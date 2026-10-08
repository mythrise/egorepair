"""Development temporal IK with native Jacobians and consistent global-C2 SQP.

All windows update ONE global node array and rebuild ONE clamped C2 curve.
No independent window curves are concatenated. Hard final model/task gates
remain mandatory, and a local failure never proves global infeasibility.
"""
import time
import numpy as np
import mujoco
from scipy.optimize import least_squares,minimize,LinearConstraint,Bounds
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation
from scipy.stats import qmc
from .continuous import JointCurve
from .tool import task_fk,opening_joint,NATIVE_SITE,PAD_MIDPOINT

class FullSolverExhausted(RuntimeError):pass

def _hat(v):
    x,y,z=v;return np.array([[0,-z,y],[z,0,-x],[-y,x,0.]])

def rotation_log_jacobian(v):
    theta=np.linalg.norm(v);H=_hat(v)
    coefficient=1/12+theta*theta/720 if theta<1e-4 else (1-.5*theta/np.tan(theta/2))/(theta*theta)
    return np.eye(3)-.5*H+coefficient*(H@H)

class NativeTaskJacobian:
    def __init__(self,adapter,position,rotation,semantics,cost,check):
        self.adapter=adapter;self.p=position;self.R=rotation;self.semantics=semantics;self.cost=cost;self.check=check;self.key=None
    def query(self,q):
        key=q.tobytes()
        if key==self.key:return self.value
        self.check();p,R=task_fk(self.adapter,q,self.semantics);self.cost['fk_calls']+=1
        m=self.adapter.model;data=self.adapter._fk_data;jp=np.zeros((3,m.nv));jr=np.zeros((3,m.nv))
        mujoco.mj_jacSite(m,data,jp,jr,self.adapter.site_id);self.cost['native_jacobian_calls']+=1
        if self.semantics==PAD_MIDPOINT:
            jacobians=[]
            for name in ('fixed_jaw_box4','moving_jaw_box2'):
                geom=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_GEOM,name);a=np.zeros((3,m.nv));b=np.zeros((3,m.nv));mujoco.mj_jacGeom(m,data,a,b,geom);jacobians.append(a);self.cost['native_jacobian_calls']+=1
            jp=np.mean(jacobians,axis=0)
        elif self.semantics!=NATIVE_SITE:raise NotImplementedError('Native task Jacobian mapping not supported')
        rv=Rotation.from_matrix(self.R.T@R).as_rotvec();residual=np.r_[(p-self.p)/.002,rv/.035]
        jac=np.vstack((jp[:,self.adapter.dof_indices]/.002,rotation_log_jacobian(rv)@self.R.T@jr[:,self.adapter.dof_indices]/.035))
        self.key=key;self.value=(residual,jac);return self.value

def cubic_control_matrices(t):
    """Linear Bernstein hulls for the SINGLE global clamped interpolant."""
    n=len(t);basis=CubicSpline(t,np.eye(n),axis=0,bc_type=((1,np.zeros(n)),(1,np.zeros(n))));a,b,c,d=basis.c;h=np.diff(t)[:,None]
    B=np.stack((d,d+c*h/3,d+2*c*h/3+b*h*h/3,d+c*h+b*h*h+a*h*h*h),axis=1)
    V=3*np.diff(B,axis=1)/h[:,None,:];A=2*np.diff(V,axis=1)/h[:,None,:]
    return B.reshape(-1,n),V.reshape(-1,n),A.reshape(-1,n),basis

def solve(adapter,target,t,parent_q,oracle,profile):
    """Bounded numeric candidate; independent FULL gates decide admissibility."""
    t=np.asarray(t,float);parent=np.asarray(parent_q,float);limits=adapter.command_limits;g=adapter.gripper_index;arm=np.asarray(adapter.arm_indices,int);rows=[target(float(x)) for x in t]
    caps=profile['solver'];options=profile['optimization'];start=time.monotonic()
    cost={'fk_calls':0,'tool_forward_calls':0,'native_jacobian_calls':0,'distance_calls':0,'ik_calls':0,'ik_evaluations':0,'sqp_iterations':0,'sqp_restarts':0,'windows':0,'alternate_branch_attempts':0}
    def check():
        if cost['fk_calls']>=caps['max_fk_calls'] or cost['distance_calls']>=caps['max_distance_calls'] or time.monotonic()-start>=caps['max_wall_s']:raise FullSolverExhausted('FULL_SOLVER_DEVELOPMENT_BUDGET_EXHAUSTED')
    def opening(q):check();cost['fk_calls']+=1;cost['tool_forward_calls']+=1;return adapter.opening_m(q)
    def geometry(q,index):
        check()
        if cost['distance_calls']+oracle.distance_cost>caps['max_distance_calls']:raise FullSolverExhausted('FULL_SOLVER_DISTANCE_BUDGET_EXHAUSTED')
        distances=oracle.distances(q,time_s=float(t[index]));cost['distance_calls']+=len(distances)
        return bool(distances) and all(np.isfinite(d) and not oracle.is_known_collision(pair,oracle.clearance_for(pair,0.)) for pair,d in distances.items())
    queries=[NativeTaskJacobian(adapter,row[0],row[1],target.tool_semantics,cost,check) for row in rows];chain=[];branches=[]
    try:
        for k,row in enumerate(rows):
            parent_width=opening(parent[k]);gripper=parent[k,g]
            if abs(parent_width-row[2])>1e-12:
                def charge():check();cost['fk_calls']+=1;cost['tool_forward_calls']+=1
                gripper=opening_joint(adapter,row[2],charge)
            seeds=[parent[k]]
            if chain:seeds.append(chain[-1])
            seeds += [parent[max(0,k-1)],parent[min(len(t)-1,k+1)]]
            for unit in qmc.Sobol(d=len(arm),scramble=False).random_base2(m=2):
                q=np.mean(limits,axis=1);q[arm]=limits[arm,0]+unit*(limits[arm,1]-limits[arm,0]);seeds.append(q)
            candidates=[];seen=set()
            for seed in seeds[:8]:
                q=np.clip(seed,limits[:,0],limits[:,1]).copy();q[g]=gripper;key=q.tobytes()
                if key in seen:continue
                seen.add(key)
                def residual(x):q[arm]=x;return queries[k].query(q)[0]
                def jac(x):q[arm]=x;return queries[k].query(q)[1][:,arm]
                fit=least_squares(residual,q[arm],jac=jac,bounds=(limits[arm,0],limits[arm,1]),max_nfev=100,ftol=1e-10,xtol=1e-10,gtol=1e-10)
                cost['ik_calls']+=1;cost['ik_evaluations']+=fit.nfev;q[arm]=fit.x;error=queries[k].query(q)[0]
                if np.linalg.norm(error[:3])>1 or np.linalg.norm(error[3:])>1 or not geometry(q,k):continue
                if chain and np.any(abs(q-chain[-1])>3*(t[k]-t[k-1])):continue
                candidates.append(q.copy())
                # First admissible nearest temporal branch is a proposal, never
                # a certificate. Full global gates are checked after joint SQP.
                if len(candidates)>=options['admissible_branches_per_node']:break
                cost['alternate_branch_attempts']+=1
            branches.append(candidates)
            if not candidates:return {'status':'LOCAL_IK_OR_TEMPORAL_BRANCH_FAIL','node':k,'cost':cost,'global_infeasibility_proven':False,'eef_retained':True}
            chain.append(min(candidates,key=lambda q:np.sum((q-parent[k])**2)+(0 if not chain else np.sum((q-chain[-1])**2))))
        Q=np.asarray(chain);B,V,A,basis=cubic_control_matrices(t);scale=limits[:,1]-limits[:,0]
        # Exact acceleration energy of a piecewise-linear q'' polynomial.
        # Gauss two-point quadrature is exact for its squared degree-two norm.
        sample=[];weights=[]
        for left,right in zip(t[:-1],t[1:]):
            mid=(left+right)/2;half=(right-left)/2;sample.extend([mid-half/np.sqrt(3),mid+half/np.sqrt(3)]);weights.extend([half,half])
        acceleration_basis=basis(np.asarray(sample),2);H=acceleration_basis.T@(np.asarray(weights)[:,None]*acceleration_basis)
        width=options['window_nodes'];overlap=options['overlap_nodes'];step=width-overlap
        for first in range(0,len(t),step):
            indices=np.arange(first,min(first+width,len(t)));cost['windows']+=1
            if len(indices)<2:continue
            # The interpolation's support is global: include ALL spans in
            # hull constraints, pruning only inequalities proven redundant
            # under the fixed variable trust box. No interval is omitted.
            original=Q.copy();seed=Q[np.ix_(indices,arm)].copy();trust=options['joint_window_trust_rad'];low=np.maximum(limits[arm,0],seed-trust);high=np.minimum(limits[arm,1],seed+trust)
            linear=[];lower=[];upper=[]
            for matrix,cap_low,cap_high in [(B,limits[arm,0],limits[arm,1]),(V,np.full(len(arm),-3.),np.full(len(arm),3.)),(A,np.full(len(arm),-100.),np.full(len(arm),100.))]:
                W=matrix[:,indices];fixed=matrix@Q[:,arm]-W@seed;center=W@((low+high)/2)+fixed;extent=abs(W)@((high-low)/2)
                for j in range(len(arm)):
                    relevant=(center[:,j]-extent[:,j]<cap_low[j])|(center[:,j]+extent[:,j]>cap_high[j]);M=np.zeros((np.sum(relevant),len(indices)*len(arm)));M[:,j::len(arm)]=W[relevant]
                    linear.append(M);lower.extend(cap_low[j]-fixed[relevant,j]);upper.extend(cap_high[j]-fixed[relevant,j])
            constraint=LinearConstraint(np.vstack(linear),lower,upper)
            def state(flat):new=Q.copy();new[np.ix_(indices,arm)]=flat.reshape(seed.shape);return new
            def objective(flat):
                check();new=state(flat);value=.2*np.sum(((new-parent)/scale)**2)+.01*np.sum(new*(H@new)/(scale**2));gradient=.4*(new-parent)/(scale**2)+.02*(H@new)/(scale**2)
                for k in indices:
                    residual,jacobian=queries[k].query(new[k]);value+=residual@residual;gradient[k]+=2*jacobian.T@residual
                return float(value),gradient[np.ix_(indices,arm)].ravel()
            def tasks(flat):
                new=state(flat);values=[];jacobians=[]
                for local,k in enumerate(indices):
                    e,j=queries[k].query(new[k]);ep=np.linalg.norm(e[:3]);er=np.linalg.norm(e[3:]);values.extend([1-ep,1-er]);jp=np.zeros(len(indices)*len(arm));jr=jp.copy();sl=slice(local*len(arm),(local+1)*len(arm));jp[sl]=0 if ep<1e-14 else -e[:3]@j[:3,arm]/ep;jr[sl]=0 if er<1e-14 else -e[3:]@j[3:,arm]/er;jacobians.extend([jp,jr])
                return np.asarray(values),np.asarray(jacobians)
            accepted=[]
            starts=[seed,parent[np.ix_(indices,arm)],.75*seed+.25*parent[np.ix_(indices,arm)],.5*seed+.5*parent[np.ix_(indices,arm)]]
            for initial in starts[:options['sqp_restarts']]:
                fit=minimize(objective,np.clip(initial,low,high).ravel(),jac=True,method='SLSQP',bounds=Bounds(low.ravel(),high.ravel()),constraints=[constraint,{'type':'ineq','fun':lambda x:tasks(x)[0],'jac':lambda x:tasks(x)[1]}],options={'maxiter':100,'ftol':1e-8})
                cost['sqp_restarts']+=1;cost['sqp_iterations']+=fit.nit
                x=fit.x;lv=constraint.A@x
                if np.all(lv>=np.asarray(lower)-1e-8) and np.all(lv<=np.asarray(upper)+1e-8) and np.min(tasks(x)[0])>=-1e-8 and all(geometry(state(x)[k],k) for k in indices):accepted.append((objective(x)[0],state(x)))
            if accepted:Q=min(accepted,key=lambda pair:pair[0])[1]
            else:Q=original
        return {'status':'NUMERIC_NONZERO_REFERENCE_CANDIDATE','q':Q,'curve':JointCurve(t,Q),'cost':cost,'whole_original_episode_covered':True,'global_infeasibility_proven':False,'eef_retained':True,'continuous_qualification':'NOT_RUN_REQUIRED_FULL_GATE','objective_optimality_claimed':False,'global_curve_window_consistency':'ONE_GLOBAL_CLAMPED_C2_INTERPOLANT_ALL_SPAN_HULL_CONSTRAINTS'}
    except FullSolverExhausted as exc:return {'status':'UNKNOWN','reason':str(exc),'cost':cost,'eef_retained':True,'global_infeasibility_proven':False}
