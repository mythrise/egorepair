"""Unassisted estimated-model MuJoCo episodes, actual states at control boundaries."""
from pathlib import Path
import xml.etree.ElementTree as ET
import hashlib
import json
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation
from a4x.robot.so101 import SO101Adapter, source_directory
from .tasks import evaluate_t1

class SO101Env:
    physics_dt=0.002
    control_dt=0.05
    substeps=25
    max_steps=400
    def __init__(self, root=None, allow_archive=False, object_position=(0.18,0.0,0.018), goal=(0.18,0.10,0.018), object_mass=0.04, object_friction=0.5, capture_rgb=False):
        self._schedule_signature=(.002,.05,25,400)
        self._validate_schedule(construction=True)
        if isinstance(object_mass,(bool,np.bool_)) or isinstance(object_friction,(bool,np.bool_)):raise ValueError('Boolean dynamics quantities forbidden')
        if not np.isfinite(object_mass) or object_mass<=0 or not np.isfinite(object_friction) or object_friction<0:
            raise ValueError('Invalid simulation dynamics assumptions')
        directory,status=source_directory(root,allow_archive)
        tree=ET.parse(directory/'so101.xml'); xml=tree.getroot()
        xml.find('compiler').set('meshdir',str((directory/'assets').resolve()))
        xml.find('option').set('timestep',str(self.physics_dt))
        world=xml.find('worldbody')
        ET.SubElement(world,'geom',name='table',type='box',size='0.5 0.5 0.02',pos='0 0 -0.02',rgba='0.5 0.5 0.5 1',friction=f'{object_friction} 0.005 0.0001')
        body=ET.SubElement(world,'body',name='task_object',pos=' '.join(map(str,object_position)))
        ET.SubElement(body,'freejoint',name='object_free')
        ET.SubElement(body,'geom',name='object_geom',type='box',size='0.012 0.012 0.018',mass=str(object_mass),friction=f'{object_friction} 0.005 0.0001',rgba='0.8 0.15 0.1 1')
        ET.SubElement(world,'light',pos='0 -0.3 0.9',dir='0 0 -1')
        ET.SubElement(world,'camera',name='workbench',pos='0.6 -0.6 0.55',xyaxes='0.707 0.707 0 -0.35 0.35 0.87',fovy='50')
        self.scene_xml=ET.tostring(xml,encoding='unicode')
        self.model=mujoco.MjModel.from_xml_string(self.scene_xml)
        self.data=mujoco.MjData(self.model)
        self.adapter=SO101Adapter(self.model)
        self.adapter.profile['source_materialization']=status
        self.object_body=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,'task_object')
        self.object_geom=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_GEOM,'object_geom')
        self.object_joint=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_JOINT,'object_free')
        self.object_qpos=self.model.jnt_qposadr[self.object_joint]
        self.object_dof=self.model.jnt_dofadr[self.object_joint]
        self.initial_object_position=np.asarray(object_position,dtype=float)
        self.goal=np.asarray(goal,dtype=float)
        self.scene_profile={'scope':'SIM_MODEL_REPLAY','data_line':'SYNTHETIC_SIM','dynamics':'SIM_ASSUMPTION','object_mass_kg':object_mass,'object_friction':object_friction,'object_inertia_source':'MuJoCo box-derived','object_half_sizes_m':[.012,.012,.018],'gravity_m_s2':self.model.opt.gravity.tolist(),'physics_dt_s':self.physics_dt,'control_dt_s':self.control_dt,'controller':'MODEL_POSITION_ZERO_ORDER_HOLD','assistance_policy':'NONE','collision_qualification':'CONTACT_LOGGING_ONLY_NOT_FULL_CONTINUOUS_CERTIFICATION','source_materialization':status}
        self.contact_contract={'source':'PINNED_SO101_MODEL_GEOMETRIES','object_geom':'object_geom',
                               'fixed_finger_geoms':[mujoco.mj_id2name(self.model,mujoco.mjtObj.mjOBJ_GEOM,i) for i in range(self.model.ngeom) if (mujoco.mj_id2name(self.model,mujoco.mjtObj.mjOBJ_GEOM,i) or '').startswith('fixed_jaw_')],
                               'moving_finger_geoms':[mujoco.mj_id2name(self.model,mujoco.mjtObj.mjOBJ_GEOM,i) for i in range(self.model.ngeom) if (mujoco.mj_id2name(self.model,mujoco.mjtObj.mjOBJ_GEOM,i) or '').startswith('moving_jaw_')]}
        self.physical_gates={'collision':'UNKNOWN','joint_limits':'UNKNOWN','velocity_limits':'UNKNOWN','contact_force_budget':'UNKNOWN','numerical_stability':'UNKNOWN','unassisted':'UNKNOWN'}
        self._frozen_signature=self._model_signature()
        self.capture_rgb=capture_rgb
        self.rgb_history=[]
        self.renderer=None
        self.reset()

    def _validate_schedule(self,construction=False):
        error=ValueError if construction else RuntimeError
        quantities=(self.physics_dt,self.control_dt,self.substeps,self.max_steps)
        if any(isinstance(x,(bool,np.bool_)) or not isinstance(x,(int,float,np.integer,np.floating)) or not np.isfinite(x) for x in quantities):raise error('Invalid runtime schedule quantity')
        if not isinstance(self.substeps,(int,np.integer)) or not isinstance(self.max_steps,(int,np.integer)) or quantities!=self._schedule_signature:raise error('Frozen runtime schedule mutation')
        if not np.isclose(self.substeps*self.physics_dt,self.control_dt,atol=1e-12,rtol=0):raise error('Inconsistent substep schedule')
        if hasattr(self,'model') and not np.isclose(self.model.opt.timestep,self.physics_dt,atol=1e-12,rtol=0):raise error('Model/runtime dt mismatch')

    def _model_signature(self):
        digest=hashlib.sha256()
        # Freeze all exposed numeric model arrays, including contacts, gains,
        # geometry, joint bounds, and assets; stepping must not mutate them.
        for name in sorted(dir(self.model)):
            value=getattr(self.model,name)
            if isinstance(value,np.ndarray):
                digest.update(name.encode());digest.update(value.tobytes())
        for name in sorted(dir(self.model.opt)):
            value=getattr(self.model.opt,name)
            if isinstance(value,np.ndarray):digest.update(name.encode());digest.update(value.tobytes())
            elif isinstance(value,(int,float,np.integer,np.floating)):digest.update(str((name,value)).encode())
        digest.update(str((self.model.neq,self.model.nmocap)).encode())
        digest.update(json.dumps([self.scene_profile,self.adapter.profile,self.contact_contract,self.physical_gates,self.scene_xml],sort_keys=True,allow_nan=False).encode())
        return digest.hexdigest()

    def _grasp_provenance(self,contacts):
        found=set(); normals={"fixed":[],"moving":[]}
        for c in contacts:
            if 'object_geom' not in (c['geom1_name'],c['geom2_name']) or c['force_on_geom2_contact_frame'][0]<=0: continue
            other=c['geom2_name'] if c['geom1_name']=='object_geom' else c['geom1_name']
            normal=np.asarray(c['frame_axes_world'])[0]*(1 if c['geom2_name']=='object_geom' else -1)
            if other in self.contact_contract['fixed_finger_geoms']:found.add('fixed');normals['fixed'].append(normal)
            if other in self.contact_contract['moving_finger_geoms']:found.add('moving');normals['moving'].append(normal)
        opposing=found=={'fixed','moving'} and any(np.dot(a,b)<-.5 for a in normals['fixed'] for b in normals['moving'])
        return {'source':'ACTUAL_MUJOCO_CONTACTS','contract':self.contact_contract,'opposing_finger_contacts':opposing}

    def reset(self,q=None):
        self._validate_schedule()
        if self._model_signature()!=self._frozen_signature: raise RuntimeError('Frozen model/profile mutation')
        mujoco.mj_resetData(self.model,self.data)
        if q is None: q=np.zeros(6); q[-1]=0.7
        q=self.adapter.validate_command(q)
        self.data.qpos[self.adapter.qpos_indices]=q
        self.data.ctrl[self.adapter.actuator_ids]=q
        # Initial-state reset is the sole object-position assignment.
        self.data.qpos[self.object_qpos:self.object_qpos+3]=self.initial_object_position
        self.data.qpos[self.object_qpos+3:self.object_qpos+7]=[1,0,0,0]
        mujoco.mj_forward(self.model,self.data)
        self.steps=0; self.commands=[]; self.states=[self.state()]
        self._boundary_qpos=self.data.qpos.copy(); self._boundary_qvel=self.data.qvel.copy(); self._boundary_time=float(self.data.time)
        self.rgb_history=[]
        if self.capture_rgb: self.rgb_history.append(self.rgb())
        return self.observation()

    def contacts(self):
        logs=[]
        for i in range(self.data.ncon):
            c=self.data.contact[i]; force=np.zeros(6); mujoco.mj_contactForce(self.model,self.data,i,force)
            logs.append({'geom1':int(c.geom1),'geom2':int(c.geom2),'geom1_name':mujoco.mj_id2name(self.model,mujoco.mjtObj.mjOBJ_GEOM,int(c.geom1)),'geom2_name':mujoco.mj_id2name(self.model,mujoco.mjtObj.mjOBJ_GEOM,int(c.geom2)),'distance_m':float(c.dist),'position_world_m':c.pos.tolist(),'force_on_geom2_contact_frame':force.tolist(),'frame_axes_world':c.frame.reshape(3,3).tolist()})
        return logs

    def state(self):
        self._validate_schedule()
        q=self.data.qpos[self.adapter.qpos_indices].copy(); contacts=self.contacts()
        object_contact=any(self.object_geom in (c['geom1'],c['geom2']) and (self.model.geom_bodyid[c['geom2'] if c['geom1']==self.object_geom else c['geom1']]) not in (0,self.object_body) for c in contacts)
        return {'time_s':float(self.data.time),'q_rad':q.tolist(),'qdot_rad_s':self.data.qvel[self.adapter.dof_indices].tolist(),'tcp_position_m':self.data.site_xpos[self.adapter.site_id].tolist(),'tcp_rotation':self.data.site_xmat[self.adapter.site_id].reshape(3,3).tolist(),'gripper_joint_rad':float(q[-1]),'opening_m':self.adapter.opening_m(q),'object_position_m':self.data.xpos[self.object_body].tolist(),'object_quaternion_wxyz':self.data.xquat[self.object_body].tolist(),'object_velocity_m_s':self.data.qvel[self.object_dof:self.object_dof+3].tolist(),'object_angular_velocity_rad_s':self.data.qvel[self.object_dof+3:self.object_dof+6].tolist(),'contacts':contacts,'robot_object_contact':object_contact,'grasp_contact_provenance':self._grasp_provenance(contacts),'assistance':bool(np.any(self.data.xfrc_applied) or np.any(self.data.qfrc_applied) or self.model.neq or self.model.nmocap),'applied_object_force':self.data.xfrc_applied[self.object_body].tolist()}

    def step(self,q_command):
        self._validate_schedule()
        if self.steps>=self.max_steps: raise RuntimeError('Episode step limit')
        if self._model_signature()!=self._frozen_signature: raise RuntimeError('Frozen model/profile mutation')
        if not np.isfinite(self.data.time) or not np.isclose(self.data.time,self._boundary_time,atol=1e-10,rtol=0): raise RuntimeError('Unauthorized clock mutation')
        if not np.array_equal(self.data.qpos,self._boundary_qpos) or not np.array_equal(self.data.qvel,self._boundary_qvel):
            raise RuntimeError('Unauthorized mid-episode state mutation')
        if np.any(self.data.xfrc_applied) or np.any(self.data.qfrc_applied):
            raise RuntimeError('External assistance is prohibited')
        q=self.adapter.validate_command(q_command)
        command={'time_s':float(self.data.time),'joint_names':list(self.adapter.joint_names),'q_command_rad':q.tolist(),'mode':'position','hold':'zero_order','duration_s':self.control_dt}
        self.data.ctrl[self.adapter.actuator_ids]=q
        self.commands.append(command)
        substep_contacts=[]
        for _ in range(self.substeps):
            mujoco.mj_step(self.model,self.data)
            contacts=self.contacts()
            substep_contacts.append({'time_s':float(self.data.time),'contacts':contacts,'assistance':bool(np.any(self.data.xfrc_applied) or np.any(self.data.qfrc_applied)),'severe_violation':bool(any(c['distance_m']<-.01 or np.linalg.norm(c['force_on_geom2_contact_frame'][:3])>1e5 for c in contacts))})
        command['substep_contacts']=substep_contacts
        self.steps+=1; self.states.append(self.state())
        if not np.all(np.isfinite(self.data.qpos)): raise RuntimeError('Nonfinite physics state')
        self._boundary_qpos=self.data.qpos.copy(); self._boundary_qvel=self.data.qvel.copy(); self._boundary_time=float(self.data.time)
        if self.capture_rgb:
            self.rgb_history.append(self.rgb()); self.rgb_history=self.rgb_history[-2:]
        return self.observation()

    def step_tcp(self,position,rotation=None,opening_m=None):
        q=self.data.qpos[self.adapter.qpos_indices].copy()
        g=q[-1] if opening_m is None else self.adapter.opening_to_joint(opening_m)
        result=self.adapter.ik(position,rotation,g,q)
        if not result.success: return {'status':'IK_FAIL','diagnostic':{'position_error_m':result.position_error_m,'rotation_error_rad':result.rotation_error_rad}}
        return {'status':'EXECUTED','observation':self.step(result.q)}

    def observation(self):
        s=self.state(); base_id=mujoco.mj_name2id(self.model,mujoco.mjtObj.mjOBJ_BODY,'base'); base_p=self.data.xpos[base_id]; base_R=self.data.xmat[base_id].reshape(3,3)
        def r6(R): return np.asarray(R)[:,:2].T.reshape(-1).tolist()
        object_R=Rotation.from_quat(np.array(s['object_quaternion_wxyz'])[[1,2,3,0]]).as_matrix()
        obj=[*(base_R.T@(np.array(s['object_position_m'])-base_p)),*r6(base_R.T@object_R),*(base_R.T@np.array(s['object_velocity_m_s'])),*(base_R.T@np.array(s['object_angular_velocity_rad_s'])),0.,0.,1.,0.,0.]
        slots=[obj]+[[0.]*20 for _ in range(3)]
        return {'profile':'SIM_STATE_V1','privileged':True,'time_s':s['time_s'],'joint_names':list(self.adapter.joint_names),'q':s['q_rad'],'qdot':s['qdot_rad_s'],'opening_m':s['opening_m'],'tcp_position_base':(base_R.T@(np.array(s['tcp_position_m'])-base_p)).tolist(),'tcp_rotation6_base':r6(base_R.T@np.array(s['tcp_rotation'])),'tcp_mask':1,'object_slots':slots,'task_id':'T1','target_object_id':'task_object','goal_region_base':(base_R.T@(self.goal-base_p)).tolist()}

    def rgb(self):
        if self.renderer is None: self.renderer=mujoco.Renderer(self.model,height=240,width=320)
        self.renderer.update_scene(self.data,camera='workbench')
        return self.renderer.render().copy()

    def rgb_observation(self):
        if not self.capture_rgb: raise RuntimeError("Enable capture_rgb before episode to preserve actual image history")
        images=self.rgb_history
        return {"profile":"ROBOT_RGB_PROPRIO_V1","time_s":float(self.data.time),"rgb_history":np.stack(([np.zeros_like(images[0])]+images) if len(images)==1 else images),"history_mask":[0,1] if len(images)==1 else [1,1],"q_rad":self.data.qpos[self.adapter.qpos_indices].copy(),"opening_m":self.adapter.opening_m(self.data.qpos[self.adapter.qpos_indices]),"task_id":"T1","goal_region_m":self.goal.copy(),"camera":"workbench"}

    def rollout(self,commands):
        for command in commands: self.step(command)
        return {'schema':'a4x.execution.v1','scene_profile':self.scene_profile,'robot_profile':self.adapter.profile,'commands':self.commands,'states':self.states,'command_count':len(self.commands),'state_count':len(self.states),'result':evaluate_t1(self.states,self.initial_object_position,self.goal,commands=self.commands,physical_gates=self.physical_gates,contact_contract=self.contact_contract),'qualification':'SIM_MODEL_ONLY'}

    def close(self):
        if self.renderer is not None: self.renderer.close(); self.renderer=None
