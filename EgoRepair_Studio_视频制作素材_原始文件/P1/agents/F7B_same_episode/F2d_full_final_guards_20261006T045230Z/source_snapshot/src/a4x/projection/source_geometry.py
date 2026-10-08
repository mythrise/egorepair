"""Readback binding of every official robot body/geom/joint/site to pinned source."""
import hashlib,json
from functools import lru_cache
import numpy as np
import mujoco
from a4x.robot.so101 import source_directory,JOINT_NAMES
from a4x.provenance import artifact_ref

def _list(a):return np.asarray(a).tolist()
def _robot_description(model,body_names):
    result=[]
    for name in body_names:
        b=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,name)
        if b<0:raise ValueError('Official source body absent')
        parent=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,int(model.body_parentid[b]));geoms=[]
        for g in range(int(model.body_geomadr[b]),int(model.body_geomadr[b]+model.body_geomnum[b])):
            fields=[mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,g),int(model.geom_type[g]),_list(model.geom_size[g]),_list(model.geom_pos[g]),_list(model.geom_quat[g]),int(model.geom_contype[g]),int(model.geom_conaffinity[g])]
            if int(model.geom_type[g])==int(mujoco.mjtGeom.mjGEOM_MESH):
                mesh=int(model.geom_dataid[g]);start=int(model.mesh_vertadr[mesh]);count=int(model.mesh_vertnum[mesh]);fields.append(hashlib.sha256(model.mesh_vert[start:start+count].tobytes()).hexdigest())
            geoms.append(fields)
        joints=[]
        for j in range(int(model.body_jntadr[b]),int(model.body_jntadr[b]+model.body_jntnum[b])):
            joints.append([mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_JOINT,j),int(model.jnt_type[j]),_list(model.jnt_pos[j]),_list(model.jnt_axis[j]),_list(model.jnt_range[j])])
        result.append([name,parent,_list(model.body_pos[b]),_list(model.body_quat[b]),geoms,joints])
    site=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_SITE,'gripperframe')
    if site<0:raise ValueError('Native tool site absent')
    result.append(['site',mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,int(model.site_bodyid[site])),_list(model.site_pos[site]),_list(model.site_quat[site])])
    for name in JOINT_NAMES:
        joint=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,name);ids=np.flatnonzero(model.actuator_trnid[:,0]==joint)
        if len(ids)!=1:raise ValueError('Official actuator mapping absent')
        result.append(['actuator',name,_list(model.actuator_ctrlrange[ids[0]])])
    result.append(['native_parent_filter',int(model.opt.disableflags)&int(mujoco.mjtDisableBit.mjDSBL_FILTERPARENT)])
    # Any added body exclusion affecting robot bodies would silently drop pairs.
    robot_ids={mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,n) for n in body_names}
    result.append(['exclusions',[int(x) for x in model.exclude_signature if int(x)>>16 in robot_ids or int(x)&65535 in robot_ids]])
    return result

@lru_cache(maxsize=1)
def _expected():
    directory,status=source_directory();model=mujoco.MjModel.from_xml_path(str(directory/'so101.xml'));names=tuple(mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,i) for i in range(1,model.nbody));description=_robot_description(model,names)
    return names,description,artifact_ref(directory/'so101.xml'),status

def verify_native_robot(model):
    # Recheck source checkout cleanliness even when compiled source readback cached.
    source_directory();names,expected,ref,status=_expected();actual=_robot_description(model,names)
    if actual!=expected:raise ValueError('Official robot geometry/kinematics/filter/tool mapping modified')
    return {'robot_source':ref,'materialization':status,'compiled_robot_sha256':hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest(),'geometry_scope':'ALL_NATIVE_SOURCE_ROBOT_GEOMS_AND_FILTERS; VISUAL_CONTYPE_ZERO_REMAINS_SOURCE_DECLARED'}

def numeric_model_digest(model):
    h=hashlib.sha256();h.update(model.names)
    for name in sorted(dir(model)):
        value=getattr(model,name)
        if isinstance(value,np.ndarray):h.update(name.encode());h.update(value.tobytes())
    for name in sorted(dir(model.opt)):
        value=getattr(model.opt,name)
        if isinstance(value,np.ndarray):h.update(name.encode());h.update(value.tobytes())
        elif isinstance(value,(int,float,np.integer,np.floating)):h.update(repr((name,value)).encode())
    return h.hexdigest()

@lru_cache(maxsize=1)
def _known_scenes():
    directory,status=source_directory();official=mujoco.MjModel.from_xml_path(str(directory/'so101.xml'))
    from a4x.sim.environment import SO101Env
    scene=SO101Env()
    return {numeric_model_digest(official):'OFFICIAL_ROBOT_ONLY',numeric_model_digest(scene.model):'FROZEN_SCENE_A_40G_FRICTION_POINT5_TABLE_OBJECT_NATIVE_GEOMETRY'}

def verify_known_scene(model):
    digest=numeric_model_digest(model)
    if digest not in _known_scenes():raise NotImplementedError('SCENE_NOT_READY_SOURCE_BOUND_COMPOSITION_RECIPE_REQUIRED')
    return {'scene_recipe':_known_scenes()[digest],'numeric_model_sha256':digest,'scope':'ESTIMATED_MODEL_REFERENCE_ONLY_NOT_REAL_WORKCELL'}

def verify_adapter_bindings(adapter):
    from a4x.robot.so101 import SO101Adapter
    if type(adapter) is not SO101Adapter or tuple(adapter.joint_names)!=JOINT_NAMES:raise ValueError('Typed native SO101 adapter required')
    m=adapter.model;ids=np.array([mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_JOINT,n) for n in JOINT_NAMES]);acts=[]
    for joint in ids:
        matches=np.flatnonzero(m.actuator_trnid[:,0]==joint)
        if len(matches)!=1:raise ValueError('Actuator mapping')
        acts.append(int(matches[0]))
    expected_limits=m.jnt_range[ids];expected_command=np.stack([np.maximum(expected_limits[:,0],m.actuator_ctrlrange[acts,0]),np.minimum(expected_limits[:,1],m.actuator_ctrlrange[acts,1])],axis=1)
    checks=[(adapter.joint_ids,ids),(adapter.qpos_indices,m.jnt_qposadr[ids]),(adapter.dof_indices,m.jnt_dofadr[ids]),(adapter.limits,expected_limits),(adapter.command_limits,expected_command),(adapter.actuator_ids,acts),(adapter.arm_indices,[0,1,2,3,4]),(adapter.tip_ids,[mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_GEOM,n) for n in ('fixed_jaw_sph_tip1','moving_jaw_sph_tip1')])]
    if adapter.gripper_index!=5 or adapter.site_id!=mujoco.mj_name2id(m,mujoco.mjtObj.mjOBJ_SITE,'gripperframe') or any(not np.array_equal(a,b) for a,b in checks):raise ValueError('Native joint/tool/limit mapping drift')
