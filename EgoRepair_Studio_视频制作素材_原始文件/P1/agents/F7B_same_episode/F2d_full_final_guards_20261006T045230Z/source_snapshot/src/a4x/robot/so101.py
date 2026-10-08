"""Adapter for the pinned official Menagerie SO101 model only."""
from pathlib import Path
import subprocess
import json
import hashlib
import xml.etree.ElementTree as ET
import numpy as np
import mujoco
from scipy.optimize import brentq
from .adapter import RobotAdapter

REVISION='4d038b3feae26ec82b46a4d586379114012a8ac7'
JOINT_NAMES=('shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll','gripper')

def source_directory(root=None, allow_archive=False):
    root=Path(root or Path(__file__).resolve().parents[3])
    repo=root/'vendor/mujoco_menagerie'
    xml=repo/'robotstudio_so101/so101.xml'
    if xml.is_file():
        rev=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
        if rev!=REVISION: raise ValueError('Menagerie source pin mismatch')
        if subprocess.check_output(['git','-C',str(repo),'status','--porcelain','--','robotstudio_so101'],text=True).strip():
            raise ValueError('Menagerie SO101 source modified')
        return xml.parent,'OFFICIAL_GIT_CHECKOUT'
    archive=root/'vendor/menagerie_so101_source_archive/robotstudio_so101'
    manifest=archive.parent/'SOURCE_ARCHIVE.json'
    if allow_archive and manifest.is_file():
        info=json.loads(manifest.read_text())
        if info['revision']!=REVISION: raise ValueError('Archive pin mismatch')
        for ref in info['artifacts']:
            file=root/ref['path']
            if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=ref['sha256']: raise ValueError('Archive file missing or changed')
        return archive,'OFFICIAL_PINNED_SOURCE_ARCHIVE_NOT_GIT_CHECKOUT'
    raise FileNotFoundError('SOURCE_NOT_MATERIALIZED: pinned Menagerie checkout absent')

class SO101Adapter(RobotAdapter):
    def __init__(self, model):
        super().__init__(model,JOINT_NAMES,'gripperframe','gripper')
        # Commands must satisfy both joint and model actuator ranges.
        self.command_limits=np.stack([np.maximum(self.limits[:,0],model.actuator_ctrlrange[self.actuator_ids,0]),np.minimum(self.limits[:,1],model.actuator_ctrlrange[self.actuator_ids,1])],axis=1)
        self.tip_ids=[mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_GEOM,n) for n in ('fixed_jaw_sph_tip1','moving_jaw_sph_tip1')]
        if min(self.tip_ids)<0: raise ValueError('Official fingertip geometry absent')
        self.profile={'robot':'SO101','source_revision':REVISION,'joint_names':list(JOINT_NAMES),'joint_units':'rad','active_arm_dof':5,'full_dof':6,'tcp':'official gripperframe','tcp_semantics':'MODEL_REFERENCE_NOT_MEASURED_TOOL','opening':'distance between official tip sphere surfaces; not parallel jaw gap','mimic':False,'controller':'official position actuators; zero-order hold','hardware_mapping':'NOT_VALIDATED','mass_inertia':'official MJCF','gain_source':'official sts3215 simulation estimates, not physical servo equivalence'}

    def opening_m(self,q):
        q=np.asarray(q,dtype=float)
        if q.shape!=(6,) or not np.all(np.isfinite(q)): raise ValueError("Invalid measured q")
        self._fk_data.qpos[self.qpos_indices]=q
        mujoco.mj_forward(self.model,self._fk_data)
        a,b=self.tip_ids
        return max(0.,float(np.linalg.norm(self._fk_data.geom_xpos[a]-self._fk_data.geom_xpos[b])-sum(self.model.geom_size[[a,b],0])))

    def opening_to_joint(self,opening_m):
        if not np.isfinite(opening_m): raise ValueError('Nonfinite opening')
        q=np.mean(self.limits,axis=1)
        lo=max(0.,self.command_limits[self.gripper_index,0]); hi=self.command_limits[self.gripper_index,1]
        def gap(v): q[self.gripper_index]=v; return self.opening_m(q)
        a,b=gap(lo),gap(hi)
        if not min(a,b)<=opening_m<=max(a,b): raise ValueError('Requested model tip gap unsupported')
        return float(brentq(lambda v:gap(v)-opening_m,lo,hi))

    def validate_command(self,q):
        q=self.validate_q(q)
        if np.any(q<self.command_limits[:,0]) or np.any(q>self.command_limits[:,1]): raise ValueError('Actuator command range exceeded')
        return q

    @classmethod
    def load(cls,root=None,allow_archive=False):
        directory,status=source_directory(root,allow_archive)
        adapter=cls(mujoco.MjModel.from_xml_path(str(directory/'so101.xml')))
        adapter.profile['source_materialization']=status
        return adapter
