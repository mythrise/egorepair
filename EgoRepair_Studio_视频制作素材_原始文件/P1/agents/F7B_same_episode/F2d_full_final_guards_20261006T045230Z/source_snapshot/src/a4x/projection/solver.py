"""Bounded temporal IK and whole-curve optimization, independent of M6."""
import time
from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares, minimize
from scipy.stats import qmc
from scipy.spatial.transform import Rotation
from .continuous import real,JointCurve

@dataclass(frozen=True)
class SolverBudget:
    max_fk_calls:int=200000
    max_distance_calls:int=20000
    max_wall_s:float=120.
    def __post_init__(self):
        for x in (self.max_fk_calls,self.max_distance_calls):
            if isinstance(x,bool) or not isinstance(x,int) or x<0:raise ValueError('Invalid solver budget')
        if isinstance(self.max_wall_s,bool) or not isinstance(self.max_wall_s,(int,float)) or not np.isfinite(self.max_wall_s) or self.max_wall_s<0:raise ValueError('Invalid wall budget')
class BudgetExhausted(RuntimeError):
    def __init__(self,cost):self.cost=cost

def project(*args,**kwargs):
    try:return _project(*args,**kwargs)
    except BudgetExhausted as e:return {'status':'UNKNOWN','reason':'SOLVER_BUDGET_EXHAUSTED','cost':e.cost,'eef_retained':True,'global_infeasibility_proven':False}

def _project(adapter,t,position,rotation,width,parent_q,*,position_tolerance=.002,rotation_tolerance=.035,velocity_limits=None,acceleration_limits=None,geometry_oracle=None,budget=None,task_curve=None,common_clock=None,tool_semantics="SO101_NATIVE_SITE_G_EQUALS_P_V1"):
    position_tolerance=float(real(position_tolerance));rotation_tolerance=float(real(rotation_tolerance))
    if position_tolerance<=0 or rotation_tolerance<=0:raise ValueError('Invalid task tolerance')
    t=real(t);p=real(position,(len(t),3));R=real(rotation,(len(t),3,3));w=real(width,(len(t),));parent=real(parent_q,(len(t),len(adapter.joint_names)))
    if len(t)<2 or np.any(np.diff(t)<=0):raise ValueError('Nonmonotone source time')
    if any(not np.allclose(x.T@x,np.eye(3),atol=1e-6) or np.linalg.det(x)<.999999 for x in R):raise ValueError('Invalid SO3')
    limits=adapter.command_limits.copy();n=limits.shape[0];g=adapter.gripper_index;arm=[i for i in range(n) if i!=g]
    velocity=real(velocity_limits if velocity_limits is not None else np.full(n,3.),(n,))
    acceleration=real(acceleration_limits if acceleration_limits is not None else np.full(n,100.),(n,))
    if np.any(velocity<=0) or np.any(acceleration<=0):raise ValueError('Derivative caps must positive')
    branches=[];cost={'tool_forward_calls':0,'fk_calls':0,'distance_calls':0,'ik_calls':0,'ik_evaluations':0,'sqp_iterations':0,'sqp_restarts':0};residuals=[];start=time.monotonic();budget=budget or SolverBudget()
    def check_budget():
        if cost['fk_calls']>=budget.max_fk_calls or cost['distance_calls']>=budget.max_distance_calls or time.monotonic()-start>budget.max_wall_s:raise BudgetExhausted(cost.copy())
    def tool_query():
        check_budget();cost['fk_calls']+=1;cost['tool_forward_calls']+=1
    def opening_query(q):
        tool_query();return adapter.opening_m(q)
    def make_curve(q,clock_t=t):
        curve=JointCurve(clock_t,q)
        if common_clock is not None:
            from .retiming import RetimedCurve
            return RetimedCurve(curve,common_clock)
        return curve
    def error(q,k):
        check_budget();cost['fk_calls']+=1
        from .tool import task_fk
        a,b=task_fk(adapter,q,tool_semantics);return np.r_[(a-p[k])/position_tolerance,Rotation.from_matrix(R[k].T@b).as_rotvec()/rotation_tolerance]
    if task_curve is not None and np.array_equal(parent,np.tile(parent[0],(len(t),1))) and tuple(task_curve.bounds(t[0],t[-1]))==(0.,0.,0.):
        exact=all(np.linalg.norm(error(parent[k],k))<1e-10 and abs(opening_query(parent[k])-w[k])<1e-12 for k in range(len(t)))
        if exact:return {'status':'PROJECTED_REFERENCE_ONLY','q':parent.copy(),'curve':make_curve(parent),'cost':cost,'eef_retained':True,'continuous_qualification':'NOT_RUN','executed':'NOT_RUN','geometry_dp':'FULL_GLOBAL_CURVE_GATE_PENDING','solver_exit':'EXACT_ZERO_OBJECTIVE_HOLD_NO_RESTART_NEEDED'}
    for k in range(len(t)):
        try:
            from .tool import opening_joint
            opening=opening_joint(adapter,w[k],tool_query)
        except ValueError:return {'status':'OUT_OF_REPRESENTATION','eef_retained':True,'cost':cost}
        seeds=[parent[k],parent[max(k-1,0)],parent[min(k+1,len(t)-1)]]
        if branches and branches[-1]:seeds.append(branches[-1][0])
        for sample in qmc.Sobol(d=len(arm),scramble=False).random_base2(m=2):
            seed=np.mean(limits,axis=1);seed[arm]=limits[arm,0]+sample*(limits[arm,1]-limits[arm,0]);seeds.append(seed)
        candidates=[];best=np.inf
        for seed in seeds[:8]:
            q=np.clip(seed,limits[:,0],limits[:,1]);q[g]=opening
            def residual(x):q[arm]=x;return error(q,k)
            fit=least_squares(residual,q[arm],bounds=(limits[arm,0],limits[arm,1]),max_nfev=100)
            cost['ik_calls']+=1;cost['ik_evaluations']+=fit.nfev;q[arm]=fit.x;err=error(q,k);best=min(best,float(np.linalg.norm(err)))
            if np.linalg.norm(err[:3])<=1 and np.linalg.norm(err[3:])<=1 and not any(np.linalg.norm(q-c)<1e-5 for c in candidates):candidates.append(q.copy())
        if geometry_oracle is not None:
            legal=[]
            for candidate in candidates:
                check_budget()
                if cost['distance_calls']+getattr(geometry_oracle,'distance_cost',1)>budget.max_distance_calls:raise BudgetExhausted(cost.copy())
                distances=geometry_oracle.distances(candidate,time_s=t[k] if common_clock is None else float(common_clock.forward(t[k]))) if getattr(geometry_oracle,'supports_time',False) else geometry_oracle.distances(candidate);cost['distance_calls']+=len(distances)
                if distances and all(np.isfinite(d) and d>=(geometry_oracle.clearance_for(pair,0.) if callable(getattr(geometry_oracle,'clearance_for',None)) else 0.) for pair,d in distances.items()):legal.append(candidate)
            candidates=legal
        branches.append(candidates);residuals.append(best)
        if not candidates:return {'status':'LOCAL_IK_FAIL','eef_retained':True,'node':k,'residuals':residuals,'cost':cost,'global_infeasibility_proven':False}
    costs=[np.array([.2*np.sum((q-parent[0])**2) for q in branches[0]])];backs=[]
    for k in range(1,len(t)):
        dt=t[k]-t[k-1] if common_clock is None else float(common_clock.forward(t[k])-common_clock.forward(t[k-1]));matrix=np.full((len(branches[k]),len(branches[k-1])),np.inf)
        for row,q in enumerate(branches[k]):
            for col,prev in enumerate(branches[k-1]):
                if not np.all(abs(q-prev)<=velocity*dt):continue
                if geometry_oracle is not None:
                    from .continuous import qualify,ContinuousProfile
                    edge=qualify(make_curve(np.array([prev,q]),t[k-1:k+1]),limits,velocity,acceleration,geometry_oracle,ContinuousProfile(max_depth=8,max_distance_calls=min(2000,budget.max_distance_calls-cost['distance_calls']),max_wall_s=max(0.,min(120.,budget.max_wall_s-(time.monotonic()-start)))))
                    cost['distance_calls']+=edge['distance_calls'];check_budget()
                    if edge['status']!='PASS':continue
                matrix[row,col]=np.sum((q-prev)**2)
        matrix+=costs[-1]
        backs.append(np.argmin(matrix,axis=1));costs.append(np.min(matrix,axis=1))
    if not np.isfinite(costs[-1]).any():return {'status':'NO_LEGAL_TEMPORAL_CHAIN','eef_retained':True,'cost':cost}
    index=int(np.argmin(costs[-1]));chain=[branches[-1][index]]
    for k in range(len(t)-2,-1,-1):index=int(backs[k][index]);chain.append(branches[k][index])
    chain=np.array(chain[::-1]);bounds=list(zip(np.tile(limits[:,0],len(t)),np.tile(limits[:,1],len(t))))
    for k in range(len(t)):bounds[k*n+g]=(chain[k,g],chain[k,g])
    def objective(flat):
        q=flat.reshape(chain.shape);curve=make_curve(q);scale=limits[:,1]-limits[:,0]
        acceleration_integral=0.
        for a,b in zip(curve.t[:-1],curve.t[1:]):
            mid=(a+b)/2;half=(b-a)/2;nodes=np.array([mid-half/np.sqrt(3),mid+half/np.sqrt(3)])
            acceleration_integral+=half*np.sum((curve(nodes,2)/scale)**2)
        return sum(np.sum(error(row,k)**2) for k,row in enumerate(q))+.2*np.sum(((q-parent)/scale)**2)+.01*acceleration_integral
    def hard_constraints(flat):
        q=flat.reshape(chain.shape);curve=make_curve(q);lo,hi=curve.bounds(curve.t[0],curve.t[-1]);vlo,vhi=curve.bounds(curve.t[0],curve.t[-1],1);alo,ahi=curve.bounds(curve.t[0],curve.t[-1],2)
        task=np.array([error(row,k) for k,row in enumerate(q)])
        return np.r_[lo-limits[:,0],limits[:,1]-hi,velocity-np.maximum(abs(vlo),abs(vhi)),acceleration-np.maximum(abs(alo),abs(ahi)),1-np.linalg.norm(task[:,:3],axis=1),1-np.linalg.norm(task[:,3:],axis=1)]
    # Fixed restart seeds; feasibility always rechecked independently.
    candidates=[]
    for seed in [chain,parent,.75*chain+.25*parent,.5*chain+.5*parent]:
        fit=minimize(objective,np.clip(seed,limits[:,0],limits[:,1]).ravel(),method='SLSQP',bounds=bounds,constraints=[{'type':'ineq','fun':hard_constraints}],options={'maxiter':100,'ftol':1e-9})
        cost['sqp_restarts']+=1;cost['sqp_iterations']+=fit.nit;q=fit.x.reshape(chain.shape)
        if np.min(hard_constraints(q.ravel()))>=-1e-8 and all(np.linalg.norm(error(row,k)[:3])<=1 and np.linalg.norm(error(row,k)[3:])<=1 for k,row in enumerate(q)) and np.allclose(q[:,g],chain[:,g],atol=1e-8):candidates.append((objective(q.ravel()),q))
    q=min(candidates,key=lambda x:x[0])[1] if candidates else chain
    return {'status':'PROJECTED_REFERENCE_ONLY','q':q,'curve':make_curve(q),'cost':cost,'eef_retained':True,'continuous_qualification':'NOT_RUN','executed':'NOT_RUN','geometry_dp':'CONTINUOUS_EDGE_CHECKED_FINAL_GLOBAL_CURVE_PENDING' if geometry_oracle is not None else 'NOT_RUN'}
