"""Exact original T1 estimated-model contact classes, not force certification."""
import json,hashlib
import numpy as np
from a4x.provenance import verify_artifact
from a4x.sim.gates import contact_classification,RECIPE

class SourceContactContract:
    SOURCE_SHA='dfddd806dd6bf57fbf38e2e556561881eebb5b7987f030b0bb54257208ca6132'
    def __init__(self,source_ref,model,root,bounds):
        path=verify_artifact(source_ref,[root])
        if source_ref['sha256']!=self.SOURCE_SHA:raise ValueError('Contact source not registered teacher05')
        data=json.loads(path.read_text());profile=data['scene_profile'];classes=profile['contact_classes'];recipe=profile['gate_recipe']
        if classes!=contact_classification(model) or recipe!=RECIPE:raise ValueError('Contact model/classes/recipe mismatch')
        t=np.array([s['time_s'] for s in data['states']]);bounds=np.asarray(bounds,float)
        if not np.array_equal(bounds,t[[0,-1]]):raise ValueError('Contact source support mismatch')
        if recipe['permitted_contact_penetration_m']!=.002:raise ValueError('Original contact depth mismatch')
        # Require actual native contact ledger, without pretending observed contact
        # timestamps define intended phase or patch ground truth.
        ledger=[c for command in data['commands'] for step in command['substep_contacts'] for c in step['contacts']]
        if not ledger:raise ValueError('Native source contact ledger missing')
        self.canonical={'time_s':t,'parent_q_rad':np.asarray([s['q_rad'] for s in data['states']],float),'object_motion_time_s':t,'object_motion_position_m':np.asarray([s['object_position_m'] for s in data['states']],float),'object_motion_quaternion_wxyz':np.asarray([s['object_quaternion_wxyz'] for s in data['states']],float)}
        self.canonical_source_digest=self.canonical_digest()
        self.source_ref=source_ref.copy();self.bounds=tuple(bounds);self.depth=.002
        self.pairs=tuple(sorted(tuple(sorted((pad,classes['object']))) for pad in classes['fixed']+classes['moving']))
        self.signature=json.dumps({'source':source_ref,'bounds':self.bounds,'pairs':self.pairs,'depth':self.depth,'classes':classes,'recipe':recipe},sort_keys=True)
    def canonical_digest(self):
        expected=('object_motion_position_m','object_motion_quaternion_wxyz','object_motion_time_s','parent_q_rad','time_s')
        if tuple(sorted(self.canonical))!=expected:raise ValueError('Canonical source keys drift')
        h=hashlib.sha256()
        for name in expected:
            value=np.asarray(self.canonical[name]);h.update(name.encode());h.update(repr((value.shape,value.dtype.str)).encode());h.update(value.tobytes())
        return h.hexdigest()
    def bind_recipe(self,recipe):
        if self.canonical_digest()!=self.canonical_source_digest:raise ValueError('Canonical source array drift')
        # Candidate z/EEF corrections remain free within their immutable source
        # profile. The scene registration, source clock and original q cannot
        # be silently replaced when borrowing teacher05 contact semantics.
        for key,value in self.canonical.items():
            if key not in recipe or not np.array_equal(np.asarray(recipe[key]),value):raise ValueError('Canonical contact source lineage mismatch: '+key)
        if str(recipe.get('object_motion_joint'))!='object_free' or str(recipe.get('object_motion_frame'))!='WORLD_METRE' or str(recipe.get('object_motion_kind'))!='SOURCE_DEFINED_MODEL_REFERENCE_NOT_M6_ACTUAL_MOTION':raise ValueError('Canonical contact object registration mismatch')
        if not np.array_equal(np.asarray(recipe['episode_bounds_s']),np.asarray(self.bounds)):raise ValueError('Canonical contact episode support mismatch')
        return {'status':'EXACT_CANONICAL_SOURCE_ARRAY_MATCH','source':self.source_ref,'original_states':len(self.canonical['time_s']),'candidate_coefficients_compared_to_zero':False}
    def clearance(self,pair,default,left,right):
        if not self.bounds[0]<=left<=right<=self.bounds[1]:raise ValueError('Contact contract outside original support')
        return -self.depth if tuple(map(int,pair.split(':'))) in self.pairs else default
