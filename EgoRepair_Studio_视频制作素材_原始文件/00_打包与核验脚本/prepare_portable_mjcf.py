"""Create a separate derived MJCF with explicit path remapping; original files stay intact.

Example: python prepare_portable_mjcf.py --bundle /path/to/extracted --source
P1/agents/.../scene.xml --output-dir /path/to/new/render_preparation
--map /home/xklv/ego_robot/a4_experiment/vendor/mujoco_menagerie/robotstudio_so101=P1/models/SO101
"""
import argparse,hashlib,json,xml.etree.ElementTree as ET
from pathlib import Path

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    a=argparse.ArgumentParser();a.add_argument('--bundle',type=Path,required=True);a.add_argument('--source',required=True);a.add_argument('--output-dir',type=Path,required=True);a.add_argument('--map',action='append',default=[]);args=a.parse_args()
    bundle=args.bundle.resolve();source=(bundle/args.source).resolve()
    if not source.is_relative_to(bundle):raise ValueError('Source must be inside extracted bundle')
    if args.output_dir.exists():raise FileExistsError('Use a new output directory')
    mappings=[]
    for rule in args.map:
        old,new=rule.split('=',1);target=(bundle/new).resolve()
        if not target.is_relative_to(bundle):raise ValueError('Mapping target must be inside bundle')
        if not target.exists():raise FileNotFoundError(target)
        mappings.append((old.rstrip('/'),str(target)))
    tree=ET.parse(source);changed=[]
    for node in tree.iter():
        for attr in ['meshdir','texturedir','assetdir','file']:
            value=node.get(attr)
            if not value:continue
            result=value
            for old,new in mappings:
                if result==old or result.startswith(old+'/'):result=new+result[len(old):]
            # Original relative references need explicit anchoring because derived XML is elsewhere.
            if attr in ['meshdir','texturedir','assetdir'] and not Path(result).is_absolute():result=str((source.parent/result).resolve())
            if node.tag=='include' and attr=='file' and not Path(result).is_absolute():result=str((source.parent/result).resolve())
            if result!=value:node.set(attr,result);changed.append({'tag':node.tag,'attribute':attr,'original':value,'derived':result})
    compiler=tree.getroot().find('compiler')
    meshdir=Path(compiler.get('meshdir','')) if compiler is not None else source.parent
    if not meshdir.is_absolute():meshdir=(source.parent/meshdir).resolve()
    mesh_checks=[]
    for mesh in tree.getroot().findall('.//asset/mesh'):
        ref=mesh.get('file')
        if ref:
            p=Path(ref) if Path(ref).is_absolute() else meshdir/ref
            if not p.is_file():raise FileNotFoundError(f'Mesh dependency unresolved: {p}')
            mesh_checks.append({'file':str(p),'sha256':digest(p)})
    args.output_dir.mkdir(parents=True)
    out=args.output_dir/source.name;tree.write(out,encoding='utf-8',xml_declaration=True)
    receipt={'original':str(source),'original_sha256':digest(source),'derived':str(out),'derived_sha256':digest(out),'changes':changed,'mesh_checks':mesh_checks,'scope':'Path remapping only; no simulation/inference and no robot-success claim.'}
    (args.output_dir/'PathRemappingReceipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'mesh_dependencies_checked':len(mesh_checks),'derived':str(out),'original_preserved':True},ensure_ascii=False))

if __name__=='__main__':main()
