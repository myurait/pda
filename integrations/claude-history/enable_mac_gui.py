#!/usr/bin/env python3
"""One-time owner review and OS onboarding for Claude-only background access."""
import argparse
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import sys
import time

LABEL='com.pda.claude-desktop-access'
DRIVER='/Applications/CuaDriver.app/Contents/MacOS/cua-driver'


def plan(home):
    base=Path(home)/'Library/Application Support/PDA/claude-history'
    manifest=Path(__file__).with_name('gui-capabilities.yaml').read_text()
    config={'Label':LABEL,'ProgramArguments':[DRIVER,'serve','--permission-mode','bounded',
             '--capability-manifest',str(base/'gui-capabilities.yaml'),'--approve-capability-manifest',
             '--no-permissions-gate'],
            'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':30,
            'EnvironmentVariables':{'CUA_TELEMETRY_ENABLED':'0'},
            'StandardOutPath':str(base/'cua.stdout.log'),'StandardErrorPath':str(base/'cua.stderr.log')}
    return {'manifest':manifest,'plist':plistlib.dumps(config),'base':base,
            'plist_path':Path(home)/'Library/LaunchAgents'/f'{LABEL}.plist',
            'socket':Path(home)/'Library/Caches/cua-driver/cua-driver.sock'}


def require_review(manifest,is_tty,response):
    if not manifest or not is_tty or response.strip().lower()!='yes':
        raise PermissionError('設定は未変更です。Mac本人のターミナルで対象設定を確認し、yes と入力してください。')


def run(args,timeout=15,check=True):
    result=subprocess.run(args,timeout=timeout,check=False,text=True,capture_output=True)
    if check and result.returncode:
        raise RuntimeError(f'{args[0]} failed (exit {result.returncode}):\n{result.stdout}\n{result.stderr}')
    return result


def wait_ready(check,timeout=15):
    deadline=time.monotonic()+timeout
    while not check():
        if time.monotonic()>=deadline:
            raise RuntimeError('Claude用CuaDriverが期限内に起動しませんでした。別のdaemonは起動していません。PDAへこの表示を伝えてください。')
        time.sleep(0.25)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inspect',action='store_true',help='Print the exact planned scope without writing or starting anything')
    a=p.parse_args();files=plan(Path.home())
    print('PDAからClaudeアプリの履歴表示・検索・新規取得セッションを操作するための、一度だけの設定です。')
    print('対象はClaudeのみ。全画面、他アプリ、ブラウザ接続、任意ファイル転送、アプリ終了は許可しません。')
    print('バックグラウンド操作を既定とし、OSの許可画面・パスワードをPDAが操作することはありません。')
    print('ログイン時に同じ制限で起動します。Macの睡眠・ロック設定は変更しません。')
    print('\n実際に適用する操作範囲:\n'+files['manifest'])
    if a.inspect:
        print('INSPECT ONLY: 設定の書込み・起動・OS許可要求は行っていません。')
        return 0
    if sys.platform!='darwin':raise RuntimeError('Mac上で実行してください。')
    if not sys.stdin.isatty():require_review(files['manifest'],False,'')
    response=input('上記の操作範囲を確認して有効化する場合だけ yes と入力: ')
    require_review(files['manifest'],sys.stdin.isatty(),response)
    if files['manifest']!=Path(__file__).with_name('gui-capabilities.yaml').read_text():
        raise RuntimeError('確認中に設定が変わりました。再度内容を確認してください。')
    run(['/usr/bin/codesign','--verify','--deep','--strict','/Applications/CuaDriver.app'])
    existing=run(['/bin/launchctl','print',f'gui/{os.getuid()}/{LABEL}'],check=False)
    if files['socket'].exists() and existing.returncode!=0:
        raise RuntimeError('別のCuaDriverが稼働しています。既存サービスは停止・上書きしません。PDAへこの表示を伝えてください。')
    for dest,data in ((files['base']/'gui-capabilities.yaml',files['manifest'].encode()),(files['plist_path'],files['plist'])):
        if dest.is_symlink() or dest.parent.resolve()!=dest.parent:
            raise RuntimeError('保存先のsymlinkは使用できません。')
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.read_bytes()!=data:
            raise RuntimeError('既存の異なる設定は上書きしません: '+str(dest))
        if not dest.exists():
            fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(data)
    os.chmod(files['base'],0o700)
    if existing.returncode!=0:
        run(['/bin/launchctl','bootstrap',f'gui/{os.getuid()}',str(files['plist_path'])])
    wait_ready(lambda: files['socket'].exists() and stat.S_ISSOCK(files['socket'].stat().st_mode)
               and run([DRIVER,'status','--socket',str(files['socket'])],timeout=3,check=False).returncode==0)
    print('\nMacの許可画面で CuaDriver の「アクセシビリティ」と「画面収録」をオンにしてください。')
    print('Terminal全体やフルディスクアクセスの許可は不要です。')
    print('権限確認を起動します。パスワードはMacのOS画面にだけ入力してください。',flush=True)
    # This product-native command owns the permission onboarding UI. The owner,
    # not an agent action, invoked this script and answers macOS prompts.
    process=subprocess.run([DRIVER,'permissions','grant'],timeout=360)
    if process.returncode:
        print('OS許可がまだ完了していません。上の表示をPDAへ伝えてください。')
        return process.returncode
    check=run([DRIVER,'permissions','status','--json'])
    print(check.stdout)
    print('ここまででOS接続の準備です。履歴全件の取得成功はPDAが別途検証します。')
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (OSError,RuntimeError,subprocess.SubprocessError) as error:
        print('ERROR: '+str(error),file=sys.stderr)
        raise SystemExit(1)
