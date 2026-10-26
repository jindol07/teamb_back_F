import java.sql.*;import java.nio.file.*;import java.util.*;
public class CameraE2EFixture {
 static final String PLATE=System.getenv("CAMERA_E2E_PLATE");
 static final Path FILE=Path.of(Objects.requireNonNull(System.getenv("CAMERA_E2E_MANIFEST"),"Explicit fixture manifest required"));
 static String resolve(String v){var m=java.util.regex.Pattern.compile("\\$\\{([^:}]+)(?::(.*))?\\}").matcher(v);return m.matches()?System.getenv().getOrDefault(m.group(1),m.group(2)==null?"":m.group(2)):v;}
 static long scalar(Connection c,String sql,Object...a)throws Exception{try(var s=c.prepareStatement(sql)){s.setQueryTimeout(5);for(int i=0;i<a.length;i++)s.setObject(i+1,a[i]);try(var r=s.executeQuery()){r.next();return r.getLong(1);}}}
 static int update(Connection c,String sql,Object...a)throws Exception{try(var s=c.prepareStatement(sql)){s.setQueryTimeout(5);for(int i=0;i<a.length;i++)s.setObject(i+1,a[i]);return s.executeUpdate();}}
 static void require(boolean b,String message){if(!b)throw new IllegalStateException(message);}
 static long id(Properties p,String key){return Long.parseLong(p.getProperty(key));}
 static void save(Properties p)throws Exception{try(var out=Files.newOutputStream(FILE)){p.store(out,"Only IDs of this synthetic HTTP verification");}}
 public static void main(String[] args)throws Exception{
  require(args.length==1&&Set.of("prepare","inspect","cleanup").contains(args[0]),"Explicit fixture mode required");
  var cfg=new Properties();try(var r=Files.newBufferedReader(Path.of("apcms_a/src/main/resources/application.properties"))){cfg.load(r);}
  String url=resolve(cfg.getProperty("spring.datasource.url"));require(PLATE!=null&&PLATE.matches("[0-9]{2,3}[가-힣][0-9]{4}"),"Explicit test plate required");require(url.equals(System.getenv("CAMERA_E2E_DB_URL")),"Unexpected DB target");
  DriverManager.setLoginTimeout(8);
  try(var c=DriverManager.getConnection(url,resolve(cfg.getProperty("spring.datasource.username")),resolve(cfg.getProperty("spring.datasource.password")))){c.setAutoCommit(false);
   try{
    var p=new Properties();if(Files.exists(FILE))try(var r=Files.newInputStream(FILE)){p.load(r);}
    if(args[0].equals("prepare")){
     require(p.isEmpty(),"Existing manifest requires inspection; do not overwrite");
     require(scalar(c,"SELECT COUNT(*) FROM VEHICLE WHERE VEHICLE_NUMBER=?",PLATE)==1&&scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=? AND EXIT_AT IS NULL",PLATE)==0&&scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE VEHICLE_NUMBER=?",PLATE)==0,"Printed vehicle is not isolated from active business; stop");
     p.setProperty("baseline_usage_count",Long.toString(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE)));
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_FLOOR WHERE FLOOR_NO=999")==0,"Synthetic floor collision");
     long office=scalar(c,"SELECT OFFICE_ID FROM VEHICLE WHERE VEHICLE_NUMBER=?",PLATE);require(office>0,"No office reference");
     for(var a:List.of(new String[]{"floor","SEQ_PARKING_FLOOR"},new String[]{"zone","SEQ_PARKING_ZONE"},new String[]{"space","SEQ_PARKING_SPACE"},new String[]{"reservation","SEQ_PARKING_RESERVATION"}))p.setProperty(a[0],Long.toString(scalar(c,"SELECT "+a[1]+".NEXTVAL FROM DUAL")));
     p.setProperty("marker","AI_HTTP_TEST_"+UUID.randomUUID().toString().substring(0,8));save(p);
     update(c,"INSERT INTO PARKING_FLOOR(PARKING_FLOOR_ID,FLOOR_NO,FLOOR_NAME) VALUES(?,999,?)",id(p,"floor"),p.getProperty("marker"));
     update(c,"INSERT INTO PARKING_ZONE(PARKING_ZONE_ID,PARKING_FLOOR_ID,ZONE_CODE,ZONE_NAME) VALUES(?,?,'Z',?)",id(p,"zone"),id(p,"floor"),p.getProperty("marker"));
     update(c,"INSERT INTO PARKING_SPACE(PARKING_SPACE_ID,PARKING_ZONE_ID,SPACE_NUMBER,SPACE_TYPE_CODE,SPACE_STATUS_CODE,MEMO) VALUES(?,?,'01','NORMAL','AVAILABLE',?)",id(p,"space"),id(p,"zone"),p.getProperty("marker"));
     update(c,"INSERT INTO PARKING_RESERVATION(PARKING_RESERVATION_ID,OFFICE_ID,PARKING_SPACE_ID,VEHICLE_NUMBER,RESERVATION_TYPE_CODE,RESERVATION_START_AT,RESERVATION_END_AT,STATUS_CODE) VALUES(?,?,?,?,'NORMAL',SYSDATE-5/1440,SYSDATE+10/1440,'CONFIRMED')",id(p,"reservation"),office,id(p,"space"),PLATE);
     c.commit();p.setProperty("committed","true");save(p);System.out.println("FIXTURE_COMMITTED=4");
    } else if(args[0].equals("inspect")){
     try(var s=c.createStatement()){s.execute("SET TRANSACTION READ ONLY");}
     System.out.println("USAGE_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE));
     if(!p.isEmpty()){
      System.out.println("LINKED_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=? AND PARKING_SPACE_ID=? AND PARKING_RESERVATION_ID=?",PLATE,id(p,"space"),id(p,"reservation")));
      System.out.println("EXITED_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=? AND EXIT_AT IS NOT NULL",PLATE));
      System.out.println("OPEN_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=? AND EXIT_AT IS NULL",PLATE));
      System.out.println("DB_LINK_VERSION="+scalar(c,"SELECT NVL(MAX(LINK_VERSION),-1) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE));
     }c.rollback();
    } else {
     require(!p.isEmpty(),"No manifest; do not delete");
     long usage=p.getProperty("usage_id")==null?0:id(p,"usage_id");
     if(usage>0)require(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=? AND (PARKING_SPACE_ID IS NULL OR PARKING_SPACE_ID=?) AND (PARKING_RESERVATION_ID IS NULL OR PARKING_RESERVATION_ID=?)",usage,PLATE,id(p,"space"),id(p,"reservation"))==1,"Verified usage ownership mismatch; stop cleanup");
     require(scalar(c,"SELECT COUNT(*) FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=? AND (RAW_PAYLOAD IS NULL OR (DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_OCCUPANCY\"')=0 AND DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_DECISION\"')=0))",id(p,"space"))==0,"Unexpected detection event on fixture; stop cleanup");
     require(scalar(c,"SELECT COUNT(*) FROM NOTIFICATION WHERE AI_DETECTION_EVENT_ID IN (SELECT AI_DETECTION_EVENT_ID FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=?)",id(p,"space"))==0,"Notification references fixture event; stop cleanup");
     require(scalar(c,"SELECT COUNT(*) FROM SAFETY_INCIDENT WHERE FIRST_AI_DETECTION_EVENT_ID IN (SELECT AI_DETECTION_EVENT_ID FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=?) OR LATEST_AI_DETECTION_EVENT_ID IN (SELECT AI_DETECTION_EVENT_ID FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=?)",id(p,"space"),id(p,"space"))==0,"Safety references fixture event; stop cleanup");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE_HISTORY WHERE PARKING_SPACE_ID=? AND CHANGE_SOURCE_CODE<>'AI'",id(p,"space"))==0,"Unexpected history on fixture; stop cleanup");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE PARKING_RESERVATION_ID=? AND (VEHICLE_NUMBER<>? OR PARKING_SPACE_ID<>?)",id(p,"reservation"),PLATE,id(p,"space"))==0,"Reservation ownership mismatch");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE WHERE PARKING_SPACE_ID=? AND (PARKING_ZONE_ID<>? OR MEMO<>? OR MEMO IS NULL)",id(p,"space"),id(p,"zone"),p.getProperty("marker"))==0,"Space ownership mismatch");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_ZONE WHERE PARKING_ZONE_ID=? AND (PARKING_FLOOR_ID<>? OR ZONE_NAME<>?)",id(p,"zone"),id(p,"floor"),p.getProperty("marker"))==0,"Zone ownership mismatch");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_FLOOR WHERE PARKING_FLOOR_ID=? AND (FLOOR_NO<>999 OR FLOOR_NAME<>?)",id(p,"floor"),p.getProperty("marker"))==0,"Floor ownership mismatch");
     int n=0;
     if(usage>0)n+=update(c,"DELETE FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=?",usage,PLATE);
     n+=update(c,"DELETE FROM PARKING_SPACE_HISTORY WHERE PARKING_SPACE_ID=? AND CHANGE_SOURCE_CODE='AI'",id(p,"space"));
     n+=update(c,"DELETE FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=? AND (DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_OCCUPANCY\"')>0 OR DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_DECISION\"')>0)",id(p,"space"));
     n+=update(c,"DELETE FROM PARKING_RESERVATION WHERE PARKING_RESERVATION_ID=? AND VEHICLE_NUMBER=? AND PARKING_SPACE_ID=?",id(p,"reservation"),PLATE,id(p,"space"));
     n+=update(c,"DELETE FROM PARKING_SPACE WHERE PARKING_SPACE_ID=? AND PARKING_ZONE_ID=? AND MEMO=?",id(p,"space"),id(p,"zone"),p.getProperty("marker"));
     n+=update(c,"DELETE FROM PARKING_ZONE WHERE PARKING_ZONE_ID=? AND PARKING_FLOOR_ID=? AND ZONE_NAME=?",id(p,"zone"),id(p,"floor"),p.getProperty("marker"));
     n+=update(c,"DELETE FROM PARKING_FLOOR WHERE PARKING_FLOOR_ID=? AND FLOOR_NO=999 AND FLOOR_NAME=?",id(p,"floor"),p.getProperty("marker"));
     c.commit();System.out.println("OWNED_SYNTHETIC_ROWS_DELETED="+n);
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE)==id(p,"baseline_usage_count")&&scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE VEHICLE_NUMBER=?",PLATE)==0&&scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE WHERE PARKING_SPACE_ID=?",id(p,"space"))==0&&scalar(c,"SELECT COUNT(*) FROM PARKING_ZONE WHERE PARKING_ZONE_ID=?",id(p,"zone"))==0&&scalar(c,"SELECT COUNT(*) FROM PARKING_FLOOR WHERE PARKING_FLOOR_ID=?",id(p,"floor"))==0,"Cleanup verification failed");
     System.out.println("REMAINING_SYNTHETIC_ROWS=0");System.out.println("PRESERVED_EXISTING_USAGE_COUNT="+p.getProperty("baseline_usage_count"));c.rollback();p.setProperty("cleaned","true");save(p);
    }
   }catch(Exception e){c.rollback();throw e;}
  }
 }
}