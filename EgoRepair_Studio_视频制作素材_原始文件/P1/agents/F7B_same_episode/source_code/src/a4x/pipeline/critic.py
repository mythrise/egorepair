"""Read actual accepted critic checkpoint and typed provenance-bound sample."""
from pathlib import Path
import json
from a4x.provenance import verify_artifact
from a4x.critics import NumericAuditReader,sim_audit_recipe,OutcomeProfile
from a4x.training.critic_train import dataset,load_critic
from a4x.models.critics import CriticConfig
from .packages import INPUT_ROOTS
from .handlers import result

def score(package,writer):
    import torch
    packet=json.loads(verify_artifact(package['inputs']['critic_input'],INPUT_ROOTS).read_text());model,checkpoint=load_critic(package['inputs']['critic_checkpoint'],INPUT_ROOTS)
    if not isinstance(packet.get('samples'),list) or not 1<=len(packet['samples'])<=8 or any(package['source_ref']['sha256'] not in s['contract']['execution_hashes'] for s in packet['samples']):raise ValueError('Bounded critic samples require actual original source ancestry')
    if model.config.visual_dim:raise ValueError('Actual bound visual features/allocation required; no zero visual placeholder')
    reader=NumericAuditReader('SIM_MODEL_REPLAY',packet['recipe_id'],sim_audit_recipe);profile=OutcomeProfile(**packet['outcome_profile'])
    if checkpoint['profile_hash']!=profile.validate():raise ValueError('Critic profile drift')
    numeric,mask,labels,records=dataset(packet['samples'],model.config,reader,profile,INPUT_ROOTS);normalizer=checkpoint['normalizer'];mean=torch.tensor(normalizer['mean']);std=torch.tensor(normalizer['std'])
    with torch.no_grad():prediction=model(torch.where(mask,(numeric-mean)/std,0.),mask)
    value={k:v.tolist() for k,v in prediction.items()};value.update(role=model.config.phase,scope=model.config.scope,checkpoint=package['inputs']['critic_checkpoint'],hard_gate_overridden=False,risk_certified=False)
    ref=writer.write_json('CriticPredictions.json',value);return result('critic',writer,[ref],{'samples':len(records),'unknown_outcomes':int((~labels['outcome_mask']).sum())},ranking_only=True)
