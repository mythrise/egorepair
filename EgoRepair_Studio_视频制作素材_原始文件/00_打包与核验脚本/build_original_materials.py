"""Build a provenance-preserving, lossless original-material ZIP. No media conversion."""
import argparse,csv,hashlib,json,os,shutil,struct,subprocess,zipfile
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone

RUN=Path('/data/xklv_data/a4_experiment/video_materials/20261008T135842_689360Z')
LIMIT=2_000_000_000
ZIPNAME='EgoRepair_Studio_视频制作素材_原始文件.zip'
ADDITIONAL=Path('/data/xklv_data/egorobot_a2/runs/egodex_additional_arms_20261002T151622_849424Z')

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def media(path):
    if path.suffix.lower()=='.png':
        with path.open('rb') as f: head=f.read(24)
        if head[:8]==b'\x89PNG\r\n\x1a\n':
            w,h=struct.unpack('>II',head[16:24]);return {'resolution':f'{w}x{h}'}
    if path.suffix.lower() in ['.jpg','.jpeg','.webp']:
        from PIL import Image
        with Image.open(path) as im:return {'resolution':f'{im.width}x{im.height}'}
    if path.suffix.lower() in ['.mp4','.mov','.webm']:
        import av
        with av.open(str(path)) as c:
            s=c.streams.video[0]
            return {'resolution':f'{s.width}x{s.height}','fps':str(s.average_rate),'duration_s':float(s.duration*s.time_base) if s.duration is not None else None}
    return {}

def load_inventory(paths):
    records=[];missing=[]
    for p in paths:
        d=json.loads(Path(p).read_text())
        if isinstance(d,list):records.extend(d)
        else:
            records.extend(d.get('records',[]));missing.extend(d.get('missing',[]));missing.extend(d.get('omitted',[]))
    return records,missing

def normalize(records):
    result=[];seen_dest={};hash_cache={};video_shas={};metadata_cache={}
    for original in records:
        row=dict(original)
        source=Path(row.get('source') or row.get('source_path') or row.get('archive_path') or '')
        if not source.is_file():raise ValueError(f'Source missing: {source}')
        dest=row.get('dest') or row.get('destination') or row.get('dest_path')
        if not dest:raise ValueError(f'Destination missing: {source}')
        dest=str(PurePosixPath(dest));parts=PurePosixPath(dest).parts
        if dest.startswith('/') or '..' in parts:raise ValueError(f'Unsafe destination: {dest}')
        stat=source.stat();key=(str(source.resolve()),stat.st_size,stat.st_mtime_ns)
        if key not in hash_cache:hash_cache[key]=sha(source)
        digest=hash_cache[key]
        expected=row.get('expected_sha256') or row.get('sha256') or row.get('source_sha256')
        if expected and expected!=digest:raise ValueError(f'Original SHA mismatch: {source}')
        if source.stat().st_mtime_ns!=stat.st_mtime_ns:raise ValueError(f'Source changed while reading: {source}')
        row.update({'source':str(source),'dest':dest,'size':stat.st_size,'sha256':digest,'priority':row.get('priority','P1'),'category':row.get('category','original'),'status':row.get('status','ORIGINAL_BYTES')})
        if source.suffix.lower() in ['.mp4','.mov','.webm','.png','.jpg','.jpeg','.webp']:
            if key not in metadata_cache:metadata_cache[key]=media(source)
            row.update(metadata_cache[key])
        if dest in seen_dest:
            if seen_dest[dest]!=digest:raise ValueError(f'Destination collision: {dest}')
            row['status']='DESTINATION_ALIAS';row['alias_of']=dest
        elif source.suffix.lower() in ['.mp4','.mov','.webm'] and digest in video_shas:
            row['status']='VIDEO_SHA_ALIAS';row['alias_of']=video_shas[digest]
        else:
            seen_dest[dest]=digest
            if source.suffix.lower() in ['.mp4','.mov','.webm']:video_shas[digest]=dest
        result.append(row)
    return result

def write_json(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inventory',action='append',required=True);ap.add_argument('--build',action='store_true');args=ap.parse_args()
    records,missing=load_inventory(args.inventory)
    records=normalize(records)
    # Independently check requested raw recordings, including tail/recovery batches.
    requested=[p for p in ADDITIONAL.rglob('*.mp4') if 'recordings' in p.parts and p.is_file()]
    included={str(Path(r['source'])) for r in records}
    gaps=[str(p) for p in requested if str(p) not in included]
    if gaps:raise ValueError('Missing raw recording source aliases: '+json.dumps(gaps,ensure_ascii=False))
    payload=[r for r in records if not r.get('alias_of')]
    summary={'files':len(payload),'source_rows':len(records),'source_bytes_before_dedup':sum(r['size'] for r in records),'payload_bytes':sum(r['size'] for r in payload),'video_aliases':sum(r['status']=='VIDEO_SHA_ALIAS' for r in records),'additional_raw_recording_paths_checked':len(requested),'additional_raw_recording_missing_paths':0,'strict_limit':LIMIT,'inventory_sources':args.inventory}
    write_json(RUN/'work/BundlePlan.json',{'summary':summary,'records':records,'missing':missing})
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if not args.build:return
    stage=RUN/'stage/materials'
    if stage.exists():raise FileExistsError(f'Refuse overwrite existing stage: {stage}')
    stage.mkdir()
    for i,row in enumerate(payload):
        dst=stage/row['dest'];dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(row['source'],dst)
        if sha(dst)!=row['sha256']:raise ValueError(f'Copy mismatch: {dst}')
        if i%1000==0:print(f'Copied {i}/{len(payload)}',flush=True)
    write_json(stage/'素材清单.json',{'summary':summary,'records':records})
    fields=['priority','category','dest','source','size','sha256','resolution','fps','duration_s','status','alias_of','original_source','original_sha256','redacted_fields','semantics']
    with (stage/'素材清单.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for r in records:writer.writerow({k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v) for k,v in r.items()})
    write_json(stage/'P0映射表.json',{'records':[r for r in records if r['priority']=='P0']})
    write_json(stage/'Missing_OmittedSize.json',{'missing_or_unavailable':missing,'omitted_for_size':[],'budget_policy':'不按尺寸自动删除。实际最终ZIP必须严格小于2,000,000,000字节；超限保留失败结果并交主agent裁定。'})
    (stage/'00_使用说明.md').write_text('''# EgoRepair Studio 视频制作素材原始文件包

本包按 P0、P1、P2 分目录，提供现有视频、标注、场景、模型和真实运行记录供剪辑及重渲染。现有素材均原字节复制；没有转码、缩放、降低帧率或截断。ZIP压缩是无损的。F10B仅使用显式脱敏副本，来源与字段处理见对应清单。

- `素材清单.csv/json`记录来源、输出路径、原始尺寸、SHA256及可取得的分辨率/帧率。相同SHA的视频仅存一份；VIDEO_SHA_ALIAS的alias_of指向实际文件。模型和场景配套目录保留相对依赖。
- `P0映射表.json`列出P0所有原文件及来源；`Missing_OmittedSize.json`记录缺失、范围限制及尺寸裁定。缺失字段或数据不会用伪造值填充。
- EgoDex原HDF5没有内部timestamp dataset；同名HDF5与视频按原frame index对齐，时间来自MP4原PTS/time_base，不宣称HDF5含时间戳。EEF数组中已有时间、开度与mask字段保持原字节及原语义。
- `P1/07_截图与图表`完整保留原档案5104普通图片及2个目录软链别名的原字节副本。原测试图片保留原路径；synthetic_red为历史测试图，不是机器人结果。
- 新Studio截图来自当前deployment_v2/site真实浏览器deviceScaleFactor=2捕获，未修改DOM数据；其CaptureManifest记录页面来源、截图时刻及错误。页面显示已有记录/示例界面，不表示此次实时API推理，也不把不同episode的录屏拼成同源物理成功。
- 机器人、物理回放和多Agent工件保留原任务/来源。请按episode与源时钟核对，失败、辅助回放与规划不得宣传为无辅助执行成功。低于720p的现有物理视频按实际尺寸列出，可使用配套模型与轨迹另行重渲染。
- basic_pick_place_117为同一302原帧场景：302帧mask/相机与12个原采样深度文件，960×540虚拟相机深度须按其原K_virtual绑定，不能直接错绑1920×1080原K。GeoJSON支持域嵌在原MultiViewTableModel.json内，观测、模型及假设域分开。
- F7B完整链按NO_EDIT连接消融范围提供；其repair_benefit为NOT_CLAIMED。F7C专家与F10B API调用分别属于独立实验，不能拼为F7B同episode云调用；真实比较标签及其他缺项见来源说明。
- 原F7 scene.xml含当时机器的绝对meshdir，原文件保持原SHA。跨机器渲染可用`00_打包与核验脚本/prepare_portable_mjcf.py`指定旧vendor目录→包内`P1/models/SO101`映射，在新输出目录生成明确派生XML及原/派生SHA回执；这仅改路径不运行物理。A1X的package://mobiman资源根指向`P1/models/A1X/mobiman`，原SO101模型保持assets相对目录。
- BGM/SFX只在有权利依据时提供；当前未找到现成授权音轨。参考截图及真实数字报告的可用性见缺失表。

生成脚本和核验结果在说明目录；核验逐项比对源/复制/ZIP解压字节SHA并检查ZIP CRC。最终大小见`2GB核验.json`及ZIP外部BuildReceipt。
''',encoding='utf-8')
    tools_dir=Path(__file__).parent
    for p in tools_dir.glob('*.py'):
        d=stage/'00_打包与核验脚本'/p.name;d.parent.mkdir(exist_ok=True);shutil.copyfile(p,d)
    file_hashes={p.relative_to(stage).as_posix():sha(p) for p in stage.rglob('*') if p.is_file()}
    write_json(stage/'SHA256SUMS.json',file_hashes)
    output=RUN/'deliverables'/ZIPNAME
    if output.exists():raise FileExistsError(output)
    with zipfile.ZipFile(output,'w',allowZip64=True) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():
                compress=zipfile.ZIP_STORED if p.suffix.lower() in ['.mp4','.mov','.webm','.png','.jpg','.jpeg','.webp','.gz','.zip','.npz','.pdf'] else zipfile.ZIP_DEFLATED
                z.write(p,p.relative_to(stage).as_posix(),compress_type=compress,compresslevel=6 if compress==zipfile.ZIP_DEFLATED else None)
    zip_size=output.stat().st_size
    # Append a fixed-length size field to allow the internal receipt to report exact final bytes.
    budget={'limit_bytes':LIMIT,'zip_bytes':f'{zip_size:010d}','strict_less_than_limit':zip_size<LIMIT,'all_existing_media_preserved':True,'lossless_zip_only':True}
    with zipfile.ZipFile(output,'a',allowZip64=True) as z:
        body=json.dumps(budget,ensure_ascii=False,indent=2)+'\n'
        dummy=zipfile.ZipInfo('2GB核验.json');dummy.compress_type=zipfile.ZIP_STORED
        # ZIP_STORED receipt length is stable; account for local header, central entry and UTF-8 name bytes.
        final_size=zip_size+len(body.encode())+76+2*len(dummy.filename.encode('utf-8'))
        budget.update(zip_bytes=f'{final_size:010d}',strict_less_than_limit=final_size<LIMIT)
        z.writestr(dummy,json.dumps(budget,ensure_ascii=False,indent=2)+'\n')
    assert output.stat().st_size==final_size,(output.stat().st_size,final_size)
    checked=0
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None,'ZIP CRC failed'
        assert len(z.namelist())==len(set(z.namelist())),'Duplicate ZIP names'
        for name,digest in file_hashes.items():
            h=hashlib.sha256()
            with z.open(name) as f:
                for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
            assert h.hexdigest()==digest,name
            checked+=1
        assert sha(stage/'SHA256SUMS.json')==hashlib.sha256(z.read('SHA256SUMS.json')).hexdigest()
    receipt={'completed_at':datetime.now(timezone.utc).isoformat(),'zip':str(output),'zip_bytes':output.stat().st_size,'zip_sha256':sha(output),'strict_limit_bytes':LIMIT,'strict_less_than_limit':output.stat().st_size<LIMIT,'zip_crc':'PASS','zip_entry_sha256_checked':checked+1,'source_copy_sha256_checked':len(payload),'summary':summary,'inventories':args.inventory}
    write_json(RUN/'work/BuildReceipt.json',receipt)
    assert output.stat().st_size<LIMIT,'Final ZIP exceeds user strict budget; root must decide omissions'
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
