"""Predeclared SO101 estimated-model execution gates, not hardware certification."""
import hashlib,json
import numpy as np
import mujoco

RECIPE={
 'recipe_id':'SO101_T1_ESTIMATED_MODEL_GATES_V1',
 'physics_dt_s':.002,'control_dt_s':.05,'substeps':25,'max_control_steps':400,
 'joint_limit_tolerance_rad':.001,'velocity_limit_rad_s':3.,
 'actuator_force_tolerance_Nm':1e-6,
 'permitted_contact_penetration_m':.002,'unintended_contact_penetration_m':.0001,
 'unintended_contact_force_N':.1,'pad_force_budget_per_side_N':60.,
 'support_contact_force_budget_N':100.,'replay_tolerance':1e-7,
 'scope':'SIM_MODEL_REPLAY_500HZ_ESTIMATED_ASSET',
 'continuous_collision_certified':False,'real_hardware_certified':False,
 'threshold_origin':'PREREGISTERED_DEVELOPMENT_SIM_ASSUMPTION_NOT_MEASURED_HARDWARE'}

def canonical_hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()

def real_array(value,shape=None):
 # Inspect leaves BEFORE NumPy can silently cast mixed bool/float lists.
 def leaves(item):
  if isinstance(item,(list,tuple)):
   for child in item:leaves(child)
  elif isinstance(item,np.ndarray):
   if item.dtype.kind not in 'iuf':raise ValueError('Nonreal physical array')
  elif isinstance(item,(bool,np.bool_)) or not isinstance(item,(int,float,np.integer,np.floating)):
   raise ValueError('Nonreal or boolean physical scalar')
 leaves(value)
 array=np.asarray(value)
 if array.dtype.kind not in 'iuf' or shape is not None and array.shape!=shape:raise ValueError('Physical array type/shape')
 return array


def boundary_matches(boundary,actual,env):
 try:
  keys=('q_rad','qdot_rad_s','object_position_m','object_quaternion_wxyz','object_velocity_m_s','object_angular_velocity_rad_s','tcp_position_m','tcp_rotation','applied_object_force')
  for key in keys:
   if not np.allclose(real_array(boundary[key],np.asarray(actual[key]).shape),actual[key],atol=1e-9,rtol=0):return False
  if not np.isclose(real_array(boundary['time_s'],()),actual['time_s'],atol=1e-9):return False
  if boundary['assistance'] is not False or actual['assistance'] is not False:return False
  if boundary['contacts']!=actual['contacts'] or boundary['grasp_contact_provenance']!=env._grasp_provenance(actual['contacts']):return False
  if not np.isclose(real_array(boundary['gripper_joint_rad'],()),actual['q_rad'][-1],atol=1e-9):return False
  if not np.isclose(real_array(boundary['opening_m'],()),env.adapter.opening_m(actual['q_rad']),atol=1e-9):return False
  obj=env.object_geom
  robot_contact=any(obj in (c['geom1'],c['geom2']) and env.model.geom_bodyid[c['geom2'] if c['geom1']==obj else c['geom1']] not in (0,env.object_body) for c in actual['contacts'])
  if type(boundary['robot_object_contact']) is not bool or boundary['robot_object_contact']!=robot_contact:return False
  return True
 except (ValueError,TypeError,KeyError,IndexError):return False


def geom_name(model,i):
 name=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_GEOM,int(i))
 if name:return name
 mesh=int(model.geom_dataid[i])
 meshname=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_MESH,mesh) if model.geom_type[i]==mujoco.mjtGeom.mjGEOM_MESH else 'primitive'
 return 'official_geom_'+str(i)+'_'+str(meshname)

def contact_classification(model):
 fixed=[];moving=[];mount=[]
 for i in range(model.ngeom):
  name=geom_name(model,i);body=mujoco.mj_id2name(model,mujoco.mjtObj.mjOBJ_BODY,int(model.geom_bodyid[i]))
  if model.geom_contype[i]==0 and model.geom_conaffinity[i]==0:continue
  if name.startswith('fixed_jaw_sph_tip') or name in ('fixed_jaw_box3','fixed_jaw_box4','fixed_jaw_box5','fixed_jaw_box6','fixed_jaw_box7') or 'wrist_roll_follower_so101_gripper_part0' in name:fixed.append(i)
  if name.startswith('moving_jaw_') or 'moving_jaw_so101_gripper_part' in name:moving.append(i)
  if body=='base':mount.append(i)
 table=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,'table');obj=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,'object_geom')
 return {'fixed':fixed,'moving':moving,'mount':mount,'table':table,'object':obj,'source':'PINNED_OFFICIAL_COLLISION_GEOMETRIES_NO_PAIR_DISABLES'}

def contacts(model,data):
 result=[]
 for i in range(data.ncon):
  c=data.contact[i];force=np.zeros(6);mujoco.mj_contactForce(model,data,i,force)
  result.append({'geom1':int(c.geom1),'geom2':int(c.geom2),'geom1_name':geom_name(model,c.geom1),'geom2_name':geom_name(model,c.geom2),'distance_m':float(c.dist),'position_world_m':c.pos.tolist(),'force_on_geom2_contact_frame':force.tolist(),'frame_axes_world':c.frame.reshape(3,3).tolist()})
 return result

def snapshot(model,data,adapter,obj_body,obj_dof):
 return {'time_s':float(data.time),'qpos_full':data.qpos.tolist(),'qvel_full':data.qvel.tolist(),
  'q_rad':data.qpos[adapter.qpos_indices].tolist(),'qdot_rad_s':data.qvel[adapter.dof_indices].tolist(),
  'ctrl_rad':data.ctrl[adapter.actuator_ids].tolist(),'actuator_force_Nm':data.actuator_force[adapter.actuator_ids].tolist(),
  'tcp_position_m':data.site_xpos[adapter.site_id].tolist(),'tcp_rotation':data.site_xmat[adapter.site_id].reshape(3,3).tolist(),
  'object_position_m':data.xpos[obj_body].tolist(),'object_quaternion_wxyz':data.xquat[obj_body].tolist(),
  'object_velocity_m_s':data.qvel[obj_dof:obj_dof+3].tolist(),'object_angular_velocity_rad_s':(data.xmat[obj_body].reshape(3,3)@data.qvel[obj_dof+3:obj_dof+6]).tolist(),
  'applied_object_force':data.xfrc_applied[obj_body].tolist(),'all_external_forces_zero':bool(not np.any(data.xfrc_applied) and not np.any(data.qfrc_applied)),
  'assistance':bool(np.any(data.xfrc_applied) or np.any(data.qfrc_applied) or model.neq or model.nmocap),'contacts':contacts(model,data)}

def check_snapshot(state,model,adapter,classification,recipe=RECIPE):
 failures=[];metrics={'pad_fixed_force_N':0.,'pad_moving_force_N':0.,'support_force_N':0.,'max_penetration_m':0.,'max_unintended_penetration_m':0.,'unintended_contact_count':0}
 try:
  numeric=('qpos_full','qvel_full','q_rad','qdot_rad_s','ctrl_rad','actuator_force_Nm','tcp_position_m','tcp_rotation','object_position_m','object_quaternion_wxyz','object_velocity_m_s','object_angular_velocity_rad_s','applied_object_force')
  if any(real_array(state[k]).dtype.kind not in 'iuf' for k in numeric):return {'status':'UNKNOWN','reason':'NONREAL_OR_BOOLEAN_PHYSICAL_LOG','metrics':metrics}
  if not all(np.all(np.isfinite(np.asarray(state[k],float))) for k in numeric):failures.append('NUMERICAL_NONFINITE')
  q=np.asarray(state['q_rad']);v=np.asarray(state['qdot_rad_s']);ctrl=np.asarray(state['ctrl_rad']);f=np.asarray(state['actuator_force_Nm'])
  if any(x.shape!=(6,) for x in (q,v,ctrl,f)):return {'status':'UNKNOWN','reason':'STATE_SHAPE','metrics':metrics}
  tol=recipe['joint_limit_tolerance_rad']
  if np.any(q<adapter.limits[:,0]-tol) or np.any(q>adapter.limits[:,1]+tol):failures.append('JOINT_LIMIT')
  if np.any(np.abs(v)>recipe['velocity_limit_rad_s']):failures.append('VELOCITY_LIMIT')
  if np.any(ctrl<adapter.command_limits[:,0]) or np.any(ctrl>adapter.command_limits[:,1]):failures.append('COMMAND_LIMIT')
  force_range=model.actuator_forcerange[adapter.actuator_ids]
  if np.any(f<force_range[:,0]-recipe['actuator_force_tolerance_Nm']) or np.any(f>force_range[:,1]+recipe['actuator_force_tolerance_Nm']):failures.append('ACTUATOR_FORCE_LIMIT')
  if state['assistance'] is not False or state['all_external_forces_zero'] is not True or np.any(state['applied_object_force']):failures.append('ASSISTANCE')
  fixed=set(classification['fixed']);moving=set(classification['moving']);pads=fixed|moving;obj=classification['object'];table=classification['table'];mount=set(classification['mount'])
  for c in state['contacts']:
   if any(real_array(c[k]).dtype.kind not in 'iuf' for k in ('distance_m','force_on_geom2_contact_frame','frame_axes_world','position_world_m')):return {'status':'UNKNOWN','reason':'NONREAL_OR_BOOLEAN_CONTACT_LOG','metrics':metrics}
   if type(c['geom1']) is not int or type(c['geom2']) is not int or np.asarray(c['frame_axes_world']).shape!=(3,3) or np.asarray(c['position_world_m']).shape!=(3,):return {'status':'UNKNOWN','reason':'CONTACT_SHAPE_OR_ID','metrics':metrics}
   if not np.isfinite(c['frame_axes_world']).all() or not np.isfinite(c['position_world_m']).all():failures.append('CONTACT_NONFINITE')
   pair={c['geom1'],c['geom2']};f=np.asarray(c['force_on_geom2_contact_frame'],float);depth=max(0.,-float(c['distance_m']))
   if f.shape!=(6,) or not np.isfinite(f).all() or not np.isfinite(depth):failures.append('CONTACT_NONFINITE');continue
   magnitude=float(np.linalg.norm(f[:3]));metrics['max_penetration_m']=max(metrics['max_penetration_m'],depth)
   support=pair=={obj,table} or table in pair and bool(pair&mount)
   pad_object=obj in pair and bool(pair&pads)
   jaw_closure=bool(pair&fixed) and bool(pair&moving)
   permitted=support or pad_object or jaw_closure
   threshold=recipe['permitted_contact_penetration_m'] if permitted else recipe['unintended_contact_penetration_m']
   if depth>threshold:failures.append('CONTACT_PENETRATION')
   if not permitted:
    metrics['max_unintended_penetration_m']=max(metrics['max_unintended_penetration_m'],depth);metrics['unintended_contact_count']+=1
   if not permitted and (depth>recipe['unintended_contact_penetration_m'] or magnitude>recipe['unintended_contact_force_N']):failures.append('UNINTENDED_CONTACT')
   if support:metrics['support_force_N']+=magnitude
   if pad_object and pair&fixed:metrics['pad_fixed_force_N']+=magnitude
   if pad_object and pair&moving:metrics['pad_moving_force_N']+=magnitude
  if max(metrics['pad_fixed_force_N'],metrics['pad_moving_force_N'])>recipe['pad_force_budget_per_side_N']:failures.append('PAD_AGGREGATE_FORCE_BUDGET')
  if metrics['support_force_N']>recipe['support_contact_force_budget_N']:failures.append('SUPPORT_FORCE_BUDGET')
 except (KeyError,TypeError,ValueError,IndexError):return {'status':'UNKNOWN','reason':'MALFORMED_SUBSTEP_EVIDENCE','metrics':metrics}
 return {'status':'FAIL' if failures else 'PASS','failures':sorted(set(failures)),'metrics':metrics}


def validate_record(record,env):
 """Real independent numeric replay. A supplied PASS receipt is never accepted."""
 unknown=lambda reason:{'status':'UNKNOWN','reason':reason,'recipe_id':RECIPE['recipe_id'],'scope':RECIPE['scope']}
 if env._model_signature()!=env._frozen_signature:return unknown('LIVE_MODEL_PROFILE_MUTATED')
 try:
  if canonical_hash(record.get('robot_profile'))!=canonical_hash(env.adapter.profile) or canonical_hash(record.get('scene_profile'))!=canonical_hash(env.scene_profile):return unknown('ROBOT_SCENE_PROFILE_BINDING')
 except (TypeError,ValueError):return unknown('MALFORMED_ROBOT_SCENE_PROFILE')
 if record.get('model_signature')!=env._frozen_signature or record.get('recipe')!=env.scene_profile['gate_recipe'] or RECIPE!=env.scene_profile['gate_recipe'] or record.get('recipe_sha256')!=canonical_hash(RECIPE):return unknown('MODEL_OR_RECIPE_BINDING')
 commands=record.get('commands');states=record.get('states');initial=record.get('initial_state')
 if not isinstance(commands,list) or not isinstance(states,list) or len(states)!=len(commands)+1 or not 0<len(commands)<=400 or not isinstance(initial,dict):return unknown('INCOMPLETE_EXECUTION')
 if initial.get('sha256')!=env.scene_profile['initial_state_sha256'] or initial.get('sha256')!=env.initial_sha256 or initial.get('state')!=env.expected_initial_state or initial.get('sha256')!=canonical_hash(initial.get('state')) or initial.get('state')!=record.get('expected_initial_state'):return unknown('INITIAL_STATE_BINDING')
 classification=env.collision_classes;data=mujoco.MjData(env.model)
 try:
  data.qpos[:]=initial['state']['qpos_full'];data.qvel[:]=initial['state']['qvel_full'];data.ctrl[env.adapter.actuator_ids]=initial['state']['ctrl_rad'];mujoco.mj_forward(env.model,data)
  initial_read=snapshot(env.model,data,env.adapter,env.object_body,env.object_dof)
  for k in ('qpos_full','qvel_full','ctrl_rad','object_position_m'):
   if not np.allclose(initial_read[k],initial['state'][k],atol=1e-9,rtol=0):return unknown('INITIAL_MODEL_READBACK')
  initial_check=check_snapshot(initial_read,env.model,env.adapter,classification)
  if initial_check['status']!='PASS':return {'status':initial_check['status'],'reason':'INITIAL_STATE_GATE','details':initial_check,'recipe_id':RECIPE['recipe_id'],'scope':RECIPE['scope']}
  if not boundary_matches(states[0],initial_read,env):return unknown('INITIAL_BOUNDARY_READBACK')
  all_checks=[];replay_error=0.;index=0
  for command_i,command in enumerate(commands):
   if command.get('mode')!='position' or command.get('hold')!='zero_order' or command.get('units','rad')!='rad':return unknown('FIXED_COMMAND_SEMANTICS')
   real_array(command['time_s'],());real_array(command['duration_s'],())
   if isinstance(command.get('time_s'),bool) or isinstance(command.get('duration_s'),bool):return unknown('BOOLEAN_COMMAND_CLOCK')
   if command.get('joint_names')!=list(env.adapter.joint_names) or not np.isclose(command['time_s'],command_i*.05,atol=1e-9) or command.get('duration_s')!=.05:return unknown('COMMAND_SCHEDULE')
   try:raw_q=real_array(command['q_command_rad'],(6,))
   except ValueError:return unknown('NONREAL_OR_BOOLEAN_COMMAND')
   if raw_q.dtype.kind not in 'iuf' or raw_q.shape!=(6,) or not np.isfinite(raw_q).all():return unknown('NONREAL_OR_BOOLEAN_COMMAND')
   q=env.adapter.validate_command(command['q_command_rad']);data.ctrl[env.adapter.actuator_ids]=q
   sub=command.get('substep_contacts')
   if not isinstance(sub,list) or len(sub)!=25:return unknown('SUBSTEP_DENOMINATOR')
   for s in sub:
    index+=1
    real_array(s['time_s'],())
    if isinstance(s.get('time_s'),bool):return unknown('BOOLEAN_SUBSTEP_CLOCK')
    if not np.isclose(s['time_s'],index*.002,atol=1e-9):return unknown('SUBSTEP_CLOCK')
    # Replay controls robot only; object is initialized once and then integrated.
    mujoco.mj_step(env.model,data);mujoco.mj_forward(env.model,data)
    actual=snapshot(env.model,data,env.adapter,env.object_body,env.object_dof)
    for key in ('qpos_full','qvel_full','q_rad','qdot_rad_s','actuator_force_Nm','ctrl_rad','tcp_position_m','tcp_rotation','object_position_m','object_quaternion_wxyz','object_velocity_m_s','object_angular_velocity_rad_s','applied_object_force'):
     claimed=real_array(s[key],np.asarray(actual[key]).shape)
     if not np.isfinite(claimed).all():return unknown('NONFINITE_REPLAY_CHANNEL')
     error=float(np.max(np.abs(np.asarray(actual[key])-claimed)));replay_error=max(replay_error,error)
    if s['assistance'] is not actual['assistance'] or s['all_external_forces_zero'] is not actual['all_external_forces_zero']:return unknown('SUBSTEP_ASSISTANCE_READBACK')
    if replay_error>RECIPE['replay_tolerance']:return unknown('INDEPENDENT_REPLAY_MISMATCH')
    if actual['contacts']!=s['contacts']:return unknown('INDEPENDENT_CONTACT_REPLAY_MISMATCH')
    all_checks.append(check_snapshot(s,env.model,env.adapter,classification))
   boundary=states[command_i+1]
   for key in ('q_rad','qdot_rad_s','object_position_m','object_quaternion_wxyz','object_velocity_m_s','object_angular_velocity_rad_s','tcp_position_m','tcp_rotation'):
    if np.asarray(boundary[key]).dtype.kind not in 'iuf' or not np.allclose(boundary[key],sub[-1][key],atol=1e-9,rtol=0):return unknown('BOUNDARY_SUBSTEP_READBACK')
   if boundary['contacts']!=sub[-1]['contacts'] or boundary['grasp_contact_provenance']!=env._grasp_provenance(sub[-1]['contacts']):return unknown('BOUNDARY_CONTACT_GRASP_READBACK')
   if boundary['assistance'] is not False or np.any(boundary['applied_object_force']):return unknown('BOUNDARY_ASSISTANCE_READBACK')
   if not np.isclose(boundary['gripper_joint_rad'],sub[-1]['q_rad'][-1],atol=1e-9) or not np.isclose(boundary['opening_m'],env.adapter.opening_m(sub[-1]['q_rad']),atol=1e-9):return unknown('BOUNDARY_TOOL_READBACK')
   if not boundary_matches(boundary,actual,env):return unknown('BOUNDARY_COMPLETE_READBACK')
  failed=[{'substep_index':i+1,'failures':c.get('failures',[]),'metrics':c['metrics']} for i,c in enumerate(all_checks) if c['status']=='FAIL']
  if any(c['status']=='UNKNOWN' for c in all_checks):return unknown('SUBSTEP_QUALIFICATION_UNKNOWN')
  aggregate={name:max((c['metrics'].get(name,0.) for c in all_checks),default=0.) for name in ('pad_fixed_force_N','pad_moving_force_N','support_force_N','max_penetration_m','max_unintended_penetration_m')}
  aggregate['unintended_contact_samples']=sum(c['metrics'].get('unintended_contact_count',0)>0 for c in all_checks)
  aggregate['max_joint_speed_rad_s']=max(float(np.max(np.abs(s['qdot_rad_s']))) for c in commands for s in c['substep_contacts'])
  aggregate['max_actuator_force_Nm']=max(float(np.max(np.abs(s['actuator_force_Nm']))) for c in commands for s in c['substep_contacts'])
  return {'status':'FAIL' if failed else 'PASS','aggregate_metrics':aggregate,'recipe_id':RECIPE['recipe_id'],'recipe_sha256':canonical_hash(RECIPE),'scope':RECIPE['scope'],'checked_substeps':index,'command_count':len(commands),'state_count':len(states),'failed_substeps':failed,'failed_substep_count':len(failed),'independent_replay_max_error':replay_error,'continuous_collision_certified':False,'hardware_certified':False}
 except (KeyError,TypeError,ValueError,IndexError):return unknown('MALFORMED_REQUIRED_EXECUTION')


def audit_artifact(execution_ref,summary_ref,allowed_roots,expected_model_signature,model_root=None):
 """F4 numerical recipe adapter. Hash-read artifacts, rebuild official model,
 independent replay, and recompute task. Never consumes caller gate PASS strings.
 """
 from a4x.provenance import verify_artifact
 from .qualified import QualifiedSO101Env
 from .tasks import evaluate_t1
 if not isinstance(expected_model_signature,str) or not expected_model_signature:return {'status':'UNKNOWN','reason':'FROZEN_EXPECTED_MODEL_REQUIRED'}
 execution_path=verify_artifact(execution_ref,allowed_roots);summary_path=verify_artifact(summary_ref,allowed_roots)
 record=json.loads(execution_path.read_text());summary=json.loads(summary_path.read_text())
 if record['model_signature']!=expected_model_signature or summary['source_refs']['execution']['sha256']!=execution_ref['sha256']:return {'status':'UNKNOWN','reason':'EXPECTED_EXECUTION_MODEL_BINDING'}
 parameter_path=verify_artifact(summary['source_refs']['parameters'],allowed_roots);parameters=json.loads(parameter_path.read_text())['scene']
 profile=record['scene_profile']
 if not np.array_equal(np.asarray(parameters['object_position'],float),profile['initial_object_position_m']) or not np.array_equal(np.asarray(parameters['goal'],float),profile['goal_world_m']) or parameters['object_mass']!=profile['object_mass_kg'] or parameters['object_friction']!=profile['object_friction']:return {'status':'UNKNOWN','reason':'ACTUAL_PARAMETER_PROFILE_BINDING'}
 env=QualifiedSO101Env(root=model_root,object_position=parameters['object_position'],goal=parameters['goal'],object_mass=parameters['object_mass'],object_friction=parameters['object_friction'])
 try:
  scene_path=verify_artifact(summary['source_refs']['scene'],allowed_roots)
  if scene_path.read_text()!=env.scene_xml:return {'status':'UNKNOWN','reason':'ACTUAL_MJCF_BINDING'}
  physical=validate_record(record,env)
  task=evaluate_t1(record['states'],env.initial_object_position,env.goal,commands=record['commands'],contact_contract=env.contact_contract)
  task['task_predicates']=dense_task_predicates(record,env)
  task['status']='FAIL' if task['task_predicates'].get('status')=='FAIL' else 'UNKNOWN'
  satisfied=task['task_predicates'].get('satisfied',False)
  from pathlib import Path
  validator_path=Path(__file__).resolve();validator_sha=hashlib.sha256(validator_path.read_bytes()).hexdigest()
  return {'validator_source':{'path':str(validator_path),'sha256':validator_sha,'kind':'IMMUTABLE_SOURCE_SNAPSHOT' if 'backups' in validator_path.parts else 'LIVE_SOURCE_NOT_FROZEN'},'status':'PASS' if physical['status']=='PASS' and satisfied else 'FAIL' if physical['status']=='FAIL' or task['status']=='FAIL' else 'UNKNOWN','recipe_id':RECIPE['recipe_id'],'recipe_sha256':canonical_hash(RECIPE),'model_signature':env._frozen_signature,'physical_qualification':physical,'task_predicates':task['task_predicates'],'source_execution_ref':execution_ref,'source_summary_ref':summary_ref,'scope':RECIPE['scope'],'data_line':'SYNTHETIC_SIM','actual_independent_numeric_replay':True,'teacher_independent_code_review':'PENDING'}
 finally:env.close()


def dense_task_predicates(record,env):
 """T1 holds checked at every actual2ms boundary, not only20Hz observations."""
 from .tasks import evaluate_t1
 source=[record['initial_state']['state']]+[s for c in record['commands'] for s in c['substep_contacts']]
 states=[]
 for raw in source:
  state=dict(raw)
  state['gripper_joint_rad']=state['q_rad'][-1]
  state['grasp_contact_provenance']=env._grasp_provenance(state['contacts'])
  states.append(state)
 result=evaluate_t1(states,env.initial_object_position,env.goal,control_dt=.002,contact_contract=env.contact_contract)
 predicate=result['task_predicates'];predicate['evaluation_hz']=500;predicate['evaluated_states']=len(states)
 for name in ('lift_end_state','place_end_state'):
  value=predicate.get(name)
  predicate[name.replace('_state','_control_boundary')]=None if value is None else int(np.ceil(value/25))
 return predicate
