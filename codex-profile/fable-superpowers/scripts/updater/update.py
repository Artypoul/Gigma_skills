"""Run explicitly or from the Codex heartbeat; code never schedules itself."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys

from core import Busy,Manager,write_json
from native import NativeBackend
from source import latest_release,stage_release

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['run','check','recover'])
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--home',type=Path,default=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex'))
    parser.add_argument('--retry',action='store_true',help='Ignore a cached compatibility hold and rerun all verification gates.')
    args=parser.parse_args()
    root,home=args.root.resolve(),args.home.resolve()
    try:
        backend=NativeBackend(root,home)
        if args.action=='check':
            manifest=json.loads((root/'.agents/plugins/marketplace.json').read_text(encoding='utf-8-sig'))
            package=root/next(x for x in manifest['plugins'] if x['name']=='superpowers')['source']['path']
            current=json.loads((package/'.codex-plugin/plugin.json').read_text(encoding='utf-8-sig'))['version']
            release=latest_release()
            from core import version_key
            result={'status':'available' if version_key(release['version'])>version_key(current) else 'unchanged','version':current,'latest':release['version'],'release':release}
        else:
            from compatibility import run_compatibility,recover_trust_leases
            recovery=lambda:recover_trust_leases(root/'updates/runs',home)
            manager=Manager(root,home,backend,run_compatibility,latest_release,stage_release,recovery=recovery,retry=args.retry)
            if args.action=='recover':
                from core import exclusive_lock
                with exclusive_lock(root/'updates/update.lock'):
                    trust=recovery()
                    result=manager.recover_pending(force=True) or ({'status':'recovered','trust_leases':trust['recovered']} if trust['recovered'] else {'status':'unchanged','reason':'No unfinished transaction.'})
            else: result=manager.run()
    except Busy:
        result={'status':'busy','new_failure':False}
    except Exception as error:
        result={'status':'failed','error_type':type(error).__name__,'reason':str(error)}
    result['checked_at_utc']=datetime.now(timezone.utc).isoformat()
    if args.action!='check':
        write_json(root/'updates/last-result.json',result)
    summary={key:value for key,value in result.items() if key not in ['checks','health','rollback_health']}
    if args.action!='check':summary['result_path']=str(root/'updates/last-result.json')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if result['status'] in ['updated','unchanged','busy','recovered','available'] or result.get('new_failure') is False else 2

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    raise SystemExit(main())
