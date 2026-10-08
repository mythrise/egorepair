"""Stage-bound compiler inputs: actual source clock and fixed read-only roots."""
import numpy as np
from a4x.provenance import verify_artifact
from .packages import INPUT_ROOTS

def bind_context(package,source,context,intent_context,geometry):
    if intent_context.get('pipeline_source_ref')!=package['source_ref'] or intent_context.get('pipeline_context_ref')!=package['context_ref']:raise ValueError('Intent original source/pipeline context binding missing')
    if context['data_line']=='SYNTHETIC_SIM':times=np.asarray([s['time_s'] for s in source['states']])
    else:
        arrays=verify_artifact(source['arrays'],INPUT_ROOTS)
        with np.load(arrays,allow_pickle=False) as a:times=a['eef_source_time_s'].copy()
    if not np.array_equal(geometry['time'],times):raise ValueError('Intent/global repair must preserve complete original source clock; partial windows cannot claim global fit')
    bound=dict(intent_context);bound['allowed_input_roots']=[str(p) for p in INPUT_ROOTS]
    return bound
