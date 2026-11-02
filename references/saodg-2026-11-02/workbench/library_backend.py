"""Read author catalog and bound covers through the shared NBT toolkit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import uuid
from toolkit import TOOLKIT
from nbt_detail_control import catalog, preview_images


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['catalog','cover']);parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--source',type=Path);parser.add_argument('--geometry');parser.add_argument('--cache',type=Path);args=parser.parse_args()
    try:
        if args.command=='catalog':result=catalog(args.workspace,cache_path=args.cache or args.workspace/'build/structure_workbench/catalog_metadata.json')
        else:
            from PIL import Image
            files=preview_images(args.source,args.geometry,1);result=dict(image=None,thumbnail=None)
            if files:
                source=Path(files[0]);key=hashlib.sha256(source.read_bytes()).hexdigest();args.cache.mkdir(parents=True,exist_ok=True);target=args.cache/(key+'.jpg')
                if not target.is_file():
                    with Image.open(source) as original:
                        thumb=original.convert('RGB');thumb.thumbnail((320,200));temporary=target.with_name(key+'.'+uuid.uuid4().hex+'.jpg');thumb.save(temporary,'JPEG',quality=78);os.replace(temporary,target)
                result=dict(image=str(source),thumbnail=str(target))
        print(json.dumps(dict(ok=True,result=result),ensure_ascii=False))
    except Exception as error:
        print(json.dumps(dict(ok=False,error=str(error)),ensure_ascii=False));return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
