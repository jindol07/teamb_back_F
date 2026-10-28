"""기존 AWS 구획의 시험 예약만 생성·조회·취소하는 JDBC 어댑터."""
import os
from pathlib import Path
import subprocess
from dotenv import dotenv_values


class DeployedFixture:
    def __init__(self, run_dir, *, reservation_required=True):
        self.root=Path(__file__).resolve().parents[4]
        self.ai=self.root/'apcms_ai'
        self.run=Path(run_dir).resolve()
        self.helper=self.ai/'ai_vision/results/parking_demo/aws_20261028/.demo_helper'
        self.cp=str(self.run)+os.pathsep+str(self.helper)+os.pathsep+(self.helper/'classpath.txt').read_text(encoding='utf-8-sig').strip()
        self.env=dict(os.environ)
        settings=dotenv_values(self.ai/'.env',encoding='utf-8-sig',interpolate=False)
        for key in ('DB_USERNAME','DB_PASSWORD'):
            if settings.get(key):self.env[key]=settings[key]
        self.env.update(DB_URL='jdbc:oracle:thin:@15.165.205.246:1521:xe',
                        DEPLOYED_DEMO_NO_RESERVATION='0' if reservation_required else '1',
                        DEPLOYED_DEMO_MANIFEST=str(self.run/'reservation.properties'),
                        CAMERA_E2E_MANIFEST=str(self.run/'reservation.properties'),CAMERA_E2E_PLATE='91소6408')

    def compile(self):
        source=Path(__file__).with_name('DeployedSpaceFixture.java')
        result=subprocess.run(['javac','-encoding','UTF-8','-cp',self.cp,'-d',str(self.run),str(source)],
                              capture_output=True,timeout=40)
        if result.returncode:raise RuntimeError('시험 예약 도우미 컴파일 실패')

    def call(self, mode, usage=None, *, entry_at=None):
        env=dict(self.env,DEPLOYED_DEMO_USAGE_ID='' if usage is None else str(usage),
                 DEPLOYED_DEMO_ENTRY_AT=entry_at or '')
        result=subprocess.run(['java','-Dfile.encoding=UTF-8','-Dstdout.encoding=UTF-8',
            '-Dstderr.encoding=UTF-8','-cp',self.cp,'DeployedSpaceFixture',mode],cwd=self.root,
            env=env,capture_output=True,text=True,encoding='utf-8',timeout=40)
        (self.run/(mode+'_db.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        if result.returncode:
            if result.returncode in (130,-1073741510,3221225786):raise KeyboardInterrupt()
            from ai_vision.parking.demo_tools.deployed_sequence import fixture_failure
            raise fixture_failure(result.stderr)
        return dict(line.split('=',1) for line in result.stdout.splitlines() if '=' in line)
