"""Native MuJoCo geom oracle with conservative articulated outer motion bounds."""
import hashlib
import numpy as np
import mujoco
from .continuous import real

class NativeDistance:
    def __init__(self,adapter,*,pairs,scope,source_error_m=0.,fixed_qpos=None,object_motions=(),allow_scene_a_support=False,contact_contract=None,first_separating_axis=False):
        self.adapter=adapter;self.model=adapter.model;self.data=mujoco.MjData(self.model)
        from .source_geometry import verify_native_robot,verify_known_scene,verify_adapter_bindings
        verify_adapter_bindings(adapter);self.source_receipt=verify_native_robot(self.model);self.source_receipt.update(verify_known_scene(self.model))
        if not isinstance(allow_scene_a_support,bool):raise ValueError('Support recipe selector must bool')
        self.support_pair=None
        if allow_scene_a_support:
            table=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_GEOM,'table');obj=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_GEOM,'object_geom')
            if min(table,obj)<0 or int(self.model.geom_bodyid[table])!=0 or int(self.model.geom_type[table])!=int(mujoco.mjtGeom.mjGEOM_BOX) or not np.allclose(self.model.geom_size[table],[.5,.5,.02]) or not np.allclose(self.model.geom_pos[table],[0,0,-.02]) or not np.allclose(self.model.geom_size[obj],[.012,.012,.018]):raise ValueError('Frozen scene A support geometry absent')
            self.support_pair=tuple(sorted((table,obj)))
        if isinstance(source_error_m,(bool,np.bool_)) or not isinstance(source_error_m,(int,float,np.integer,np.floating)):raise ValueError('Source error must real non-Boolean')
        from .contact_contract import SourceContactContract
        if contact_contract is not None and type(contact_contract) is not SourceContactContract:raise ValueError('Typed source contact contract required')
        if not isinstance(first_separating_axis,bool):raise ValueError("Axis policy must bool")
        self.first_separating_axis=first_separating_axis
        self.contact_contract=contact_contract;self.current_interval=None;self.current_time=None
        self.scope=str(scope);self.error=float(source_error_m)
        if not np.isfinite(self.error) or self.error<0:raise ValueError('Invalid source error')
        self.pairs=tuple((int(a),int(b)) for a,b in pairs);self.distance_cost=len(self.pairs)
        if self.pairs!=native_pairs(self.model):raise ValueError('Native full pair set cannot be pruned or reordered')
        if not self.pairs or any(a==b or min(a,b)<0 or max(a,b)>=self.model.ngeom for a,b in self.pairs):raise ValueError('Invalid pair set')
        if fixed_qpos is not None:self.data.qpos[:]=real(fixed_qpos,(self.model.nq,))
        # Freejoint/moving environmental bodies require externally registered bounds.
        self.environment_unbound=any(int(self.model.jnt_type[j])==int(mujoco.mjtJoint.mjJNT_FREE) for j in range(self.model.njnt))
        self.fixed_environment=self.data.qpos.copy();self.environment_indices=np.array([i for i in range(self.model.nq) if i not in adapter.qpos_indices],dtype=int)
        from .object_motion import ObjectMotion
        self.motions={}
        for motion in object_motions:
            if not isinstance(motion,ObjectMotion):raise ValueError('Typed registered object curve required')
            j=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_JOINT,motion.joint_name)
            if j<0 or int(self.model.jnt_type[j])!=int(mujoco.mjtJoint.mjJNT_FREE) or j in self.motions:raise ValueError('Invalid object joint binding')
            address=int(self.model.jnt_qposadr[j])
            if not np.allclose(motion.pose(motion.curve.t[0]),self.fixed_environment[address:address+7],atol=1e-10,rtol=0):raise ValueError('Object curve frozen initial state mismatch')
            self.motions[j]=motion
        self.supports_time=True;self.expected_environment=self.fixed_environment.copy()
        self.model_digest=self._signature();self.cache={};self.native_cache={};self.object_bound_cache={};self.actual_distance_calls=0;self.cache_hits=0;self.forward_calls=0;self.radius=self._radii();self.weights={};self.geom_free_joints={}
        for geom in {x for pair in self.pairs for x in pair}:
            body=int(self.model.geom_bodyid[geom]);ancestors=[];path=[];free=[]
            while body:
                path.append(body)
                for j in range(self.model.body_jntadr[body],self.model.body_jntadr[body]+self.model.body_jntnum[body]):
                    if j in adapter.joint_ids:ancestors.append(j)
                    elif int(self.model.jnt_type[j])==int(mujoco.mjtJoint.mjJNT_FREE):free.append(j)
                body=int(self.model.body_parentid[body])
            # Triangle inequality upper bound on every ancestor-axis to every point.
            radius=sum(np.linalg.norm(self.model.body_pos[x]) for x in path)+sum(2*np.linalg.norm(self.model.jnt_pos[j]) for j in ancestors)+np.linalg.norm(self.model.geom_pos[geom])+self.radius[geom]
            self.geom_free_joints[geom]=tuple(free)
            self.weights[geom]=np.array([radius if j in ancestors else 0. for j in adapter.joint_ids])
        self.model_digest=self._signature()
    def _array_signature(self,name,array):
        sealed=getattr(self,'sealed_model_arrays',None)
        if sealed is None:return array.tobytes()
        if name not in sealed:return array.tobytes()
        original,digest,descriptor=sealed[name]
        actual=(array.__array_interface__['data'][0],array.shape,array.strides,array.dtype.str)
        if array is not original or array.flags.writeable or descriptor!=actual:raise ValueError('SEALED_MODEL_ARRAY_CONTEXT_DRIFT')
        return digest
    def _signature(self):
        h=hashlib.sha256()
        for name in sorted(dir(self.model)):
            a=getattr(self.model,name)
            if isinstance(a,np.ndarray):h.update(name.encode());h.update(self._array_signature('model.'+name,a))
        for name in sorted(dir(self.model.opt)):
            a=getattr(self.model.opt,name)
            if isinstance(a,np.ndarray):h.update(name.encode());h.update(self._array_signature('opt.'+name,a))
            elif isinstance(a,(int,float,np.integer,np.floating)):h.update(repr((name,a)).encode())
        if hasattr(self,'radius'):h.update(np.asarray(self.radius).tobytes())
        if hasattr(self,'weights'):
            for geom in sorted(self.weights):h.update(str(geom).encode());h.update(self.weights[geom].tobytes())
            h.update(repr(self.geom_free_joints).encode())
        for value in (self.adapter.joint_ids,self.adapter.qpos_indices,self.adapter.dof_indices,self.adapter.limits,self.adapter.command_limits,self.adapter.arm_indices,np.asarray(self.adapter.actuator_ids),np.asarray(self.adapter.tip_ids)):h.update(value.tobytes())
        h.update(repr(self.first_separating_axis).encode())
        h.update(repr(None if self.contact_contract is None else (self.contact_contract.signature,self.contact_contract.canonical_digest(),self.contact_contract.source_ref,self.contact_contract.bounds,self.contact_contract.depth,self.contact_contract.pairs)).encode())
        h.update(repr((self.adapter.site_id,self.adapter.gripper_index,self.adapter.joint_names,self.pairs,self.distance_cost,self.scope,self.error,self.support_pair,self.source_receipt,self.adapter.profile,tuple((j,m.digest) for j,m in self.motions.items()))).encode());return h.hexdigest()
    def _radii(self):
        radii=[]
        for i,kind in enumerate(self.model.geom_type):
            kind=int(kind)
            s=self.model.geom_size[i]
            if kind==mujoco.mjtGeom.mjGEOM_MESH:
                mesh=int(self.model.geom_dataid[i]);start=int(self.model.mesh_vertadr[mesh]);count=int(self.model.mesh_vertnum[mesh]);r=np.max(np.linalg.norm(self.model.mesh_vert[start:start+count],axis=1))
            elif kind==mujoco.mjtGeom.mjGEOM_SPHERE:r=s[0]
            elif kind==mujoco.mjtGeom.mjGEOM_CAPSULE:r=s[0]+s[1]
            elif kind in (mujoco.mjtGeom.mjGEOM_BOX,mujoco.mjtGeom.mjGEOM_ELLIPSOID,mujoco.mjtGeom.mjGEOM_CYLINDER):r=np.linalg.norm(s)
            else:r=np.inf
            radii.append(float(r))
        return radii
    def distances(self,q,time_s=None):
        if self._signature()!=self.model_digest:raise ValueError('MODEL_OR_SCOPE_DRIFT')
        if not np.array_equal(self.data.qpos[self.environment_indices],self.expected_environment[self.environment_indices]):raise ValueError('SCENE_BINDING_DRIFT')
        if any(j not in self.motions for free in self.geom_free_joints.values() for j in free):raise NotImplementedError('MOVING_OBJECT_POSE_AND_BOUND_NOT_REGISTERED')
        self.current_time=time_s;self.current_interval=None
        q=real(q,(len(self.adapter.joint_names),))
        for j,motion in self.motions.items():
            if time_s is None:raise ValueError('REGISTERED_OBJECT_TIME_REQUIRED')
            address=int(self.model.jnt_qposadr[j]);self.data.qpos[address:address+7]=motion.pose(time_s)
        self.expected_environment=self.data.qpos.copy()
        key=(self.model_digest,q.tobytes(),self.data.qpos.tobytes(),time_s)
        if key not in self.cache:
            self.data.qpos[self.adapter.qpos_indices]=q;mujoco.mj_forward(self.model,self.data);self.forward_calls+=1
            distances={};self.last_native_distances={}
            for a,b in self.pairs:
                self.actual_distance_calls+=1;segment=np.zeros(6);native=float(mujoco.mj_geomDistance(self.model,self.data,a,b,1e6,segment));name=f'{a}:{b}';self.last_native_distances[name]=native
                if native<0:distances[name]=native;continue
                ray=segment[3:]-segment[:3];length=np.linalg.norm(ray)
                if length<=1e-15:ray=self.data.geom_xpos[b]-self.data.geom_xpos[a];length=np.linalg.norm(ray)
                if length<=1e-15:distances[name]=np.nan;continue
                axis=ray/length;axes=[axis]
                basis_a=self.data.geom_xmat[a].reshape(3,3);basis_b=self.data.geom_xmat[b].reshape(3,3)
                axes.extend(basis_a.T);axes.extend(basis_b.T)
                axes.extend(np.cross(x,y) for x in basis_a.T for y in basis_b.T)
                try:
                    lower=-np.inf
                    for axis_index,direction in enumerate(axes):
                        norm=np.linalg.norm(direction)
                        if norm<1e-12:continue
                        direction=direction/norm;amin,amax=self._support(a,direction);bmin,bmax=self._support(b,direction)
                        lower=max(lower,max(bmin-amax,amin-bmax)/(1+16*np.finfo(float).eps))
                        if self.first_separating_axis and axis_index==0 and lower>0:break
                    distances[name]=lower
                except NotImplementedError:distances[name]=np.nan
            self.cache[key]=distances;self.native_cache[key]=self.last_native_distances.copy()
        else:self.cache_hits+=1
        self.last_native_distances=self.native_cache[key].copy()
        return self.cache[key]
    def _support(self,geom,axis):
        # Exact native convex support; outward floating-point inflation is separate
        # from the user-declared model/source error in displacement_bound.
        center=self.data.geom_xpos[geom];matrix=self.data.geom_xmat[geom].reshape(3,3);local=matrix.T@axis;s=self.model.geom_size[geom];kind=int(self.model.geom_type[geom]);projection=float(axis@center)
        if kind==int(mujoco.mjtGeom.mjGEOM_BOX):radius=float(abs(local)@s)
        elif kind==int(mujoco.mjtGeom.mjGEOM_SPHERE):radius=float(s[0])*np.linalg.norm(axis)
        elif kind==int(mujoco.mjtGeom.mjGEOM_CAPSULE):radius=float(s[0])*np.linalg.norm(axis)+float(s[1])*abs(local[2])
        elif kind==int(mujoco.mjtGeom.mjGEOM_CYLINDER):radius=float(s[0])*np.linalg.norm(local[:2])+float(s[1])*abs(local[2])
        elif kind==int(mujoco.mjtGeom.mjGEOM_ELLIPSOID):radius=float(np.linalg.norm(s*local))
        elif kind==int(mujoco.mjtGeom.mjGEOM_MESH):
            mesh=int(self.model.geom_dataid[geom]);start=int(self.model.mesh_vertadr[mesh]);count=int(self.model.mesh_vertnum[mesh]);values=self.model.mesh_vert[start:start+count]@local+projection
            error=64*np.finfo(float).eps*(1+float(np.max(abs(values))))
            return float(np.min(values))-error,float(np.max(values))+error
        else:raise NotImplementedError('NATIVE_GEOMETRY_SUPPORT_NOT_IMPLEMENTED')
        error=64*np.finfo(float).eps*(1+abs(projection)+radius)
        return projection-radius-error,projection+radius+error
    def is_known_collision(self,pair,clearance):return self.last_native_distances.get(pair,np.inf)<clearance
    def clearance_for(self,pair,default):
        clearance=-.002 if tuple(map(int,pair.split(':')))==self.support_pair else default
        if self.contact_contract is not None:
            left,right=self.current_interval or (self.current_time,self.current_time)
            clearance=self.contact_contract.clearance(pair,clearance,left,right)
        return clearance
    def interval_displacement_bounds(self,dq,left,right):
        if self._signature()!=self.model_digest:raise ValueError('BOUND_MODEL_OR_SCOPE_DRIFT')
        self.current_interval=(left,right)
        bounds={f'{a}:{b}':self._displacement_bound(f'{a}:{b}',dq,left,right) for a,b in self.pairs}
        if self._signature()!=self.model_digest:raise ValueError('BOUND_MODEL_OR_SCOPE_DRIFT')
        return bounds
    def displacement_bound(self,pair,dq,left,right):
        if self._signature()!=self.model_digest:raise ValueError('BOUND_MODEL_OR_SCOPE_DRIFT')
        return self._displacement_bound(pair,dq,left,right)
    def _displacement_bound(self,pair,dq,left,right):
        a,b=map(int,pair.split(':'))
        free=set(self.geom_free_joints[a]+self.geom_free_joints[b])
        if any(j not in self.motions for j in free):raise NotImplementedError('MOVING_OBJECT_BOUND_NOT_REGISTERED')
        object_bound=0.
        for geom in (a,b):
            for j in self.geom_free_joints[geom]:
                motion=self.motions[j];radius=self.radius[geom]+np.linalg.norm(self.model.geom_pos[geom])
                if motion._digest()!=motion.digest:raise ValueError('OBJECT_CURVE_DRIFT')
                key=(motion.digest,left,right)
                if key not in self.object_bound_cache:self.object_bound_cache[key]=(motion.motion_bound(left,right),motion.angular_bound(left,right))
                translation,angular=self.object_bound_cache[key]
                object_bound+=translation+radius*angular
        if not np.all(np.isfinite(self.weights[a])) or not np.all(np.isfinite(self.weights[b])):raise NotImplementedError('UNBOUNDED_GEOMETRY')
        return float((self.weights[a]+self.weights[b])@dq+self.error+object_bound)

def native_pairs(model):
    """Native bitmask/weld/parent/explicit body exclusion scope, unchanged geometry."""
    excluded=set()
    for sig in model.exclude_signature:
        excluded.add((int(sig)>>16,int(sig)&65535))
    pairs=[]
    for a in range(model.ngeom):
        for b in range(a+1,model.ngeom):
            if not ((int(model.geom_contype[a])&int(model.geom_conaffinity[b])) or (int(model.geom_contype[b])&int(model.geom_conaffinity[a]))):continue
            ba=int(model.body_weldid[model.geom_bodyid[a]]);bb=int(model.body_weldid[model.geom_bodyid[b]])
            if ba==bb or tuple(sorted((ba,bb))) in excluded:continue
            # Native parent filter is disabled only by the corresponding model flag.
            filter_parent=not (int(model.opt.disableflags)&int(mujoco.mjtDisableBit.mjDSBL_FILTERPARENT))
            if filter_parent and (int(model.body_parentid[ba])==bb or int(model.body_parentid[bb])==ba) and min(ba,bb)>0:continue
            pairs.append((a,b))
    return tuple(pairs)
