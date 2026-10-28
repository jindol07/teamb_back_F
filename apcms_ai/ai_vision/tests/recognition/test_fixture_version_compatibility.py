"""실제 Java 도우미를 모의 JDBC로 검사합니다. 업무 DB에 연결하지 않습니다."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


HARNESS = r'''
import java.lang.reflect.*;
import java.sql.*;
public class FixtureVersionHarness {
 static int metadataQueries=0, versionQueries=0;
 static Object defaultValue(Class<?> type){
  if(type==boolean.class)return false;
  if(type==int.class)return 0;
  if(type==long.class)return 0L;
  return null;
 }
 static <T>T mock(Class<T> type,InvocationHandler handler){
  return type.cast(Proxy.newProxyInstance(type.getClassLoader(),new Class[]{type},handler));
 }
 static Connection connection(int count,boolean fail){
  return mock(Connection.class,(proxy,method,args)->{
   if(method.getName().equals("prepareStatement")){
    String sql=(String)args[0];
    boolean metadata=sql.contains("USER_TAB_COLUMNS");
    if(!sql.startsWith("SELECT "))throw new AssertionError("Mutation attempted");
    if(metadata){metadataQueries++;if(fail)throw new SQLException("Metadata failed");}
    else {versionQueries++;if(count==0)throw new AssertionError("Missing column was queried");}
    return mock(PreparedStatement.class,(p,m,a)->{
     if(m.getName().equals("executeQuery"))return mock(ResultSet.class,(r,f,v)->{
      if(f.getName().equals("next"))return true;
      if(f.getName().equals("getLong"))return metadata?(long)count:4L;
      return defaultValue(f.getReturnType());
     });
     return defaultValue(m.getReturnType());
    });
   }
   throw new AssertionError("Unexpected connection operation: "+method.getName());
  });
 }
 public static void main(String[] args)throws Exception{
  String mode=args[0];
  if(mode.equals("clock")){
   var window=CameraE2EFixture.reservationWindow(java.time.Instant.parse("2026-10-27T23:59:00Z"));
   if(!window[0].toLocalDateTime().toString().equals("2026-10-28T08:54") || !window[1].toLocalDateTime().toString().equals("2026-10-28T09:09"))throw new AssertionError("Reservation clock mismatch");
   System.out.println("KST_WINDOW_VERIFIED");
  }else if(mode.equals("error")){
   try{CameraE2EFixture.inspectLinkVersion(connection(1,true),"91소6408");throw new AssertionError("Error hidden");}
   catch(SQLException expected){System.out.println("ERROR_PROPAGATED");}
  }else{
   int count=mode.equals("absent")?0:1;
   System.out.println(CameraE2EFixture.inspectLinkVersion(connection(count,false),"91소6408"));
   if(metadataQueries!=1||versionQueries!=count)throw new AssertionError("Unexpected query count");
  }
 }
}
'''


class FixtureVersionCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('java') or not shutil.which('javac'):
            raise unittest.SkipTest('실제 Java 도우미 검증에는 JDK가 필요합니다.')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        harness = cls.root / 'FixtureVersionHarness.java'
        harness.write_text(HARNESS, encoding='utf-8')
        source = Path(__file__).resolve().parents[2] / 'parking/demo_tools/CameraE2EFixture.java'
        compiled = subprocess.run(['javac', '-encoding', 'UTF-8', '-d', str(cls.root), str(source), str(harness)],
                                  capture_output=True, text=True, encoding='utf-8', timeout=30)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)

    def run_case(self, mode):
        result = subprocess.run(['java', '-cp', str(self.root), 'FixtureVersionHarness', mode],
            env=dict(os.environ, CAMERA_E2E_MANIFEST=str(self.root / 'unused.properties')),
            capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_missing_optional_column_is_explicitly_unverified(self):
        output = self.run_case('absent')
        self.assertIn('DB_LINK_VERSION=UNAVAILABLE', output)
        self.assertIn('NOT_RUN_COLUMN_MISSING', output)

    def test_present_column_keeps_original_version_inspection(self):
        self.assertIn('DB_LINK_VERSION=4', self.run_case('present'))

    def test_metadata_error_is_not_disguised_as_optional_column_absence(self):
        self.assertIn('ERROR_PROPAGATED', self.run_case('error'))

    def test_fixture_reservation_uses_boot_korean_time_across_utc_date_boundary(self):
        self.assertIn('KST_WINDOW_VERIFIED', self.run_case('clock'))
