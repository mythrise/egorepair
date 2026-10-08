"""Model-specific MuJoCo kinematics; no hardware equivalence is claimed."""
from dataclasses import dataclass
import numpy as np
import mujoco
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

@dataclass
class IKResult:
    q: np.ndarray
    position_error_m: float
    rotation_error_rad: float
    success: bool
    evaluations: int

class RobotAdapter:
    def __init__(self, model, joint_names, tcp_site, gripper_joint):
        self.model = model
        self.joint_names = tuple(joint_names)
        self.joint_ids = np.array([mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, n) for n in joint_names])
        self.site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, tcp_site)
        if np.any(self.joint_ids < 0) or self.site_id < 0:
            raise ValueError('Declared robot joints/TCP absent in actual model')
        if any(model.jnt_type[j] != mujoco.mjtJoint.mjJNT_HINGE for j in self.joint_ids):
            raise ValueError('Adapter requires hinge joint model')
        self.qpos_indices = model.jnt_qposadr[self.joint_ids]
        self.dof_indices = model.jnt_dofadr[self.joint_ids]
        self.limits = model.jnt_range[self.joint_ids].copy()
        self.gripper_index = self.joint_names.index(gripper_joint)
        self.arm_indices = np.array([i for i in range(len(joint_names)) if i != self.gripper_index])
        self.actuator_ids = []
        for j in self.joint_ids:
            ids = np.flatnonzero(model.actuator_trnid[:,0] == j)
            if len(ids) != 1:
                raise ValueError('Requires exactly one actuator per active joint')
            self.actuator_ids.append(int(ids[0]))
        self._fk_data = mujoco.MjData(model)

    def validate_q(self, q):
        q = np.asarray(q, dtype=float)
        if q.shape != (len(self.joint_names),) or not np.all(np.isfinite(q)):
            raise ValueError('Invalid q shape or nonfinite values')
        if np.any(q < self.limits[:,0]) or np.any(q > self.limits[:,1]):
            raise ValueError('Joint limits exceeded')
        return q

    def fk(self, q):
        q = self.validate_q(q)
        self._fk_data.qpos[self.qpos_indices] = q
        mujoco.mj_forward(self.model, self._fk_data)
        return self._fk_data.site_xpos[self.site_id].copy(), self._fk_data.site_xmat[self.site_id].reshape(3,3).copy()

    def ik(self, position, rotation=None, opening_joint_rad=None, seed=None, position_tolerance=0.002, rotation_tolerance=0.035):
        p = np.asarray(position, dtype=float)
        if p.shape != (3,) or not np.all(np.isfinite(p)):
            raise ValueError('Invalid target position')
        target_R = None if rotation is None else np.asarray(rotation, dtype=float)
        if target_R is not None and (target_R.shape != (3,3) or not np.allclose(target_R.T@target_R,np.eye(3),atol=1e-6) or not np.isclose(np.linalg.det(target_R),1)):
            raise ValueError('Target rotation must be SO(3)')
        q0 = self.validate_q(np.mean(self.limits,axis=1) if seed is None else seed).copy()
        if opening_joint_rad is not None:
            q0[self.gripper_index] = opening_joint_rad
            self.validate_q(q0)
        def residual(arm):
            q = q0.copy(); q[self.arm_indices] = arm
            pos, R = self.fk(q)
            parts = [pos-p]
            if target_R is not None:
                parts.append(0.05*Rotation.from_matrix(target_R.T@R).as_rotvec())
            return np.concatenate(parts)
        result = least_squares(residual, q0[self.arm_indices], bounds=(self.limits[self.arm_indices,0],self.limits[self.arm_indices,1]),max_nfev=300,xtol=1e-10,ftol=1e-10,gtol=1e-10)
        q = q0.copy(); q[self.arm_indices] = result.x
        actual_p, actual_R = self.fk(q)
        pe = float(np.linalg.norm(actual_p-p)); re = 0.0 if target_R is None else float(Rotation.from_matrix(target_R.T@actual_R).magnitude())
        return IKResult(q, pe, re, pe <= position_tolerance and re <= rotation_tolerance, result.nfev)

    def qualify_trajectory(self, q, times, position_targets=None):
        q=np.asarray(q); times=np.asarray(times)
        if q.ndim != 2 or q.shape[1] != len(self.joint_names) or times.shape!=(len(q),) or not np.all(np.isfinite(times)) or np.any(np.diff(times)<=0):
            raise ValueError('Invalid trajectory/timestamps')
        limit_mask=np.all(np.isfinite(q)&(q>=self.limits[:,0])&(q<=self.limits[:,1]),axis=1)
        positions=np.full((len(q),3),np.nan)
        for i in np.flatnonzero(limit_mask): positions[i]=self.fk(q[i])[0]
        return {'scope':'ROBOT_MODEL_REFERENCE','joint_names':list(self.joint_names),'limit_mask':limit_mask,'fk_position':positions,'velocity_rad_s':np.diff(q,axis=0)/np.diff(times)[:,None], 'collision_qualified':False, 'controller_velocity_limit_qualified':False}
