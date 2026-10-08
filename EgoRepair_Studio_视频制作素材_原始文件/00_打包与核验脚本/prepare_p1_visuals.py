"""Inventory original visual assets. Preserve the entire 07 archive subtree."""
import hashlib,json
from pathlib import Path

ROOT=Path('/home/xklv/ego_robot/a4_experiment')
RUN=Path('/data/xklv_data/a4_experiment/video_materials/20261008T135842_689360Z')
MAT=Path('/data/xklv_data/a4_experiment/material_archive/20261008T055932Z')
CONTEST=Path('/data/xklv_data/a4_experiment/contest_submission/20261008T092641_413022Z')
M7=Path('/data/xklv_data/a4_experiment/site_updates/m7_robot_trajectories_20261008T103155_169104Z')

def main():
    records=[]; missing=[]
    archive={}
    for line in (MAT/'00_说明与清单/all_artifacts.jsonl').read_text().splitlines():
        row=json.loads(line)
        if (row.get('archive_relative') or '').startswith('07_截图与图表/'):
            archive[row['archive_relative']]=row
    def add(p,dest,category,**extra):
        records.append({'source':str(p),'dest':dest,'priority':'P1','category':category,'status':'ORIGINAL_BYTES',**extra})
    shots=list((MAT/'07_截图与图表').rglob('*'))
    shots=[p for p in shots if p.is_file()]
    regular=[p for p in shots if not p.is_symlink()]
    assert len(regular)==5104,(len(regular),'original full shots count changed')
    assert sum(p.stat().st_size for p in regular)==98051738
    for p in sorted(shots):
        rel=p.relative_to(MAT).as_posix()
        row=archive.get(rel,{})
        assert row or p.is_symlink(),'unmapped shot '+str(p)
        add(p,'P1/'+rel,'archive_complete_shots',original_source=row.get('source_resolved'),expected_sha256=row.get('archive_sha256'),archive_symlink_alias=p.is_symlink(),semantics='原档案synthetic_red测试图片，非真实机器人输出' if p.name=='synthetic_red.png' else '')
    for p in sorted((CONTEST/'upload').iterdir()):
        if p.suffix.lower() in ['.jpg','.pdf']:
            add(p,'P1/比赛最新截图与文档/'+p.name,'contest_current_visuals')
    for p in sorted((CONTEST/'work/screenshots').glob('*.png')):
        add(p,'P1/比赛最新截图与文档/原始PNG/'+p.name,'contest_raw_png')
    for group in ['browser_layout','browser_layout_v2']:
        for p in sorted((M7/'work'/group).glob('*.png')):
            add(p,'P1/M7桌面手机原截图/'+group+'/'+p.name,'m7_original_screenshots')
    for name in ['favicon.svg','hands-poster.webp','hands-rgba.mp4','background.mp4','ego_original_poster.jpg','robot_policy_F_poster.jpg','a1x_planning_trajectory_poster.jpg']:
        p=ROOT/'deployment_v2/site/media'/name
        if p.is_file(): add(p,'P1/品牌原资产/'+name,'brand_original')
        else: missing.append({'priority':'P1','item':name,'status':'NOT_FOUND'})
    missing += [{'priority':'P1','item':'独立彩虹光环静态原图','status':'NOT_FOUND','note':'现有品牌资源为background.mp4；无生成替代图。'}, {'priority':'P2','item':'既有授权BGM或音效','status':'NOT_FOUND','note':'未发现附授权依据的现成BGM/SFX；旧片静音。'}]
    capture=RUN/'work/native_2xdpi/CaptureManifest.json'
    if capture.exists():
        data=json.loads(capture.read_text())
        records.extend(data['records'])
        add(capture,'P1/Studio_新2xDPI截图/CaptureManifest.json','capture_provenance')
    else: missing.append({'priority':'P1','item':'Studio原生2xDPI截图','status':'CAPTURE_PENDING'})
    for folder,names in [('p0_inventory',['P0Readme.txt','Summary.json','Missing.json','P0Inventory.json','RawRecordingsSupplement.json']),('p1_inventory',['README_P1.txt','ModelDependencyCheck.json','P1Inventory.json'])]:
        for name in names:
            p=RUN/'work'/folder/name
            if p.is_file():add(p,'00_来源与配套说明/'+folder+'/'+name,'provenance_and_semantic_limits')
    output=RUN/'work/p1_visual_inventory.json'
    output.write_text(json.dumps({'records':records,'missing':missing,'full_archive_shots_count':len(shots),'full_archive_shots_bytes':sum(p.stat().st_size for p in shots)},ensure_ascii=False,indent=2))
    print(json.dumps({'records':len(records),'bytes':sum(Path(r['source']).stat().st_size for r in records),'output':str(output)},ensure_ascii=False))

if __name__=='__main__':main()
