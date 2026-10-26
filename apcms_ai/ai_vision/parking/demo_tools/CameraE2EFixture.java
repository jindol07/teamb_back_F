import java.sql.*;import java.nio.file.*;import java.util.*;
public class CameraE2EFixture {
 static final String PLATE=System.getenv("CAMERA_E2E_PLATE");
 static final Path FILE=Path.of(Objects.requireNonNull(System.getenv("CAMERA_E2E_MANIFEST"),"Explicit fixture manifest required"));
 static String resolve(String v){var m=java.util.regex.Pattern.compile("\\$\\{([^:}]+)(?::(.*))?\\}").matcher(v);return m.matches()?System.getenv().getOrDefault(m.group(1),m.group(2)==null?"":m.group(2)):v;}
 static long scalar(Connection c,String sql,Object...a)throws Exception{try(var s=c.prepareStatement(sql)){s.setQueryTimeout(5);for(int i=0;i<a.length;i++)s.setObject(i+1,a[i]);try(var r=s.executeQuery()){r.next();return r.getLong(1);}}}
 static int update(Connection c,String sql,Object...a)throws Exception{try(var s=c.prepareStatement(sql)){s.setQueryTimeout(5);for(int i=0;i<a.length;i++)s.setObject(i+1,a[i]);return s.executeUpdate();}}
 static void require(boolean b,String message){if(!b)throw new IllegalStateException(message);}
 static long id(Properties p,String key){return Long.parseLong(p.getProperty(key));}
 static List<Long> spaces(Properties p){var result=new ArrayList<Long>();result.add(id(p,"space"));if(p.getProperty("wrong_space")!=null){long wrong=id(p,"wrong_space");require(wrong>0&&wrong!=id(p,"space"),"Invalid second space");result.add(wrong);}return result;}
 static List<Long> usages(Properties p){
  int cycles=Integer.parseInt(p.getProperty("cycles","1"));require(cycles==1||cycles==2,"Invalid manifest cycles");
  require(!(p.containsKey("usage_id")&&p.containsKey("usage_ids")),"Mixed usage formats");
  require(cycles==2||!p.containsKey("usage_ids"),"Multiple usages require repeat manifest");
  require(cycles==1||!p.containsKey("usage_id"),"Repeat manifest requires usage list");
  String raw=p.getProperty(cycles==2?"usage_ids":"usage_id","");var result=new ArrayList<Long>();
  if(!raw.isEmpty())for(String value:raw.split(",",-1)){require(value.matches("[1-9][0-9]*"),"Invalid usage ID");long usage=Long.parseLong(value);require(!result.contains(usage),"Duplicate usage ID");result.add(usage);}
  require(result.size()<=cycles,"Too many owned usages");return result;
 }
 static void save(Properties p)throws Exception{try(var out=Files.newOutputStream(FILE)){p.store(out,"Only IDs of this synthetic HTTP verification");}}
 public static void main(String[] args)throws Exception{
  require(args.length==1&&Set.of("prepare","inspect","cleanup").contains(args[0]),"Explicit fixture mode required");
  String scenario=System.getenv().getOrDefault("CAMERA_E2E_SCENARIO","normal");
  require(Set.of("normal","wrong_space_correction").contains(scenario),"Invalid scenario");
  String cycles=System.getenv().getOrDefault("CAMERA_E2E_CYCLES","1");
  require(Set.of("1","2").contains(cycles)&&(!cycles.equals("2")||scenario.equals("normal")),"Invalid repeat scope");
  var cfg=new Properties();try(var r=Files.newBufferedReader(Path.of("apcms_a/src/main/resources/application.properties"))){cfg.load(r);}
  String url=resolve(cfg.getProperty("spring.datasource.url"));require(PLATE!=null&&PLATE.matches("[0-9]{2,3}[가-힣][0-9]{4}"),"Explicit test plate required");require(url.equals(System.getenv("CAMERA_E2E_DB_URL")),"Unexpected DB target");
  DriverManager.setLoginTimeout(8);
  try(var c=DriverManager.getConnection(url,resolve(cfg.getProperty("spring.datasource.username")),resolve(cfg.getProperty("spring.datasource.password")))){c.setAutoCommit(false);
   try{
    var p=new Properties();if(Files.exists(FILE))try(var r=Files.newInputStream(FILE)){p.load(r);}
    if(args[0].equals("prepare")){
     require(p.isEmpty(),"Existing manifest requires inspection; do not overwrite");
     require(scalar(c,"SELECT COUNT(*) FROM VEHICLE WHERE VEHICLE_NUMBER=?",PLATE)==1&&scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=? AND EXIT_AT IS NULL",PLATE)==0&&scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE VEHICLE_NUMBER=?",PLATE)==0,"Printed vehicle is not isolated from active business; stop");
     p.setProperty("cycles",cycles);
     p.setProperty("baseline_usage_count",Long.toString(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE)));
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_FLOOR WHERE FLOOR_NO=999")==0,"Synthetic floor collision");
     long office=scalar(c,"SELECT OFFICE_ID FROM VEHICLE WHERE VEHICLE_NUMBER=?",PLATE);require(office>0,"No office reference");
     for(var a:List.of(new String[]{"floor","SEQ_PARKING_FLOOR"},new String[]{"zone","SEQ_PARKING_ZONE"},new String[]{"space","SEQ_PARKING_SPACE"},new String[]{"reservation","SEQ_PARKING_RESERVATION"}))p.setProperty(a[0],Long.toString(scalar(c,"SELECT "+a[1]+".NEXTVAL FROM DUAL")));
     if(scenario.equals("wrong_space_correction"))p.setProperty("wrong_space",Long.toString(scalar(c,"SELECT SEQ_PARKING_SPACE.NEXTVAL FROM DUAL")));
     p.setProperty("marker","AI_HTTP_TEST_"+UUID.randomUUID().toString().substring(0,8));save(p);
     update(c,"INSERT INTO PARKING_FLOOR(PARKING_FLOOR_ID,FLOOR_NO,FLOOR_NAME) VALUES(?,999,?)",id(p,"floor"),p.getProperty("marker"));
     update(c,"INSERT INTO PARKING_ZONE(PARKING_ZONE_ID,PARKING_FLOOR_ID,ZONE_CODE,ZONE_NAME) VALUES(?,?,'Z',?)",id(p,"zone"),id(p,"floor"),p.getProperty("marker"));
     update(c,"INSERT INTO PARKING_SPACE(PARKING_SPACE_ID,PARKING_ZONE_ID,SPACE_NUMBER,SPACE_TYPE_CODE,SPACE_STATUS_CODE,MEMO) VALUES(?,?,'01','NORMAL','AVAILABLE',?)",id(p,"space"),id(p,"zone"),p.getProperty("marker"));
     if(p.getProperty("wrong_space")!=null)update(c,"INSERT INTO PARKING_SPACE(PARKING_SPACE_ID,PARKING_ZONE_ID,SPACE_NUMBER,SPACE_TYPE_CODE,SPACE_STATUS_CODE,MEMO) VALUES(?,?,'02','NORMAL','AVAILABLE',?)",id(p,"wrong_space"),id(p,"zone"),p.getProperty("marker"));
     update(c,"INSERT INTO PARKING_RESERVATION(PARKING_RESERVATION_ID,OFFICE_ID,PARKING_SPACE_ID,VEHICLE_NUMBER,RESERVATION_TYPE_CODE,RESERVATION_START_AT,RESERVATION_END_AT,STATUS_CODE) VALUES(?,?,?,?,'NORMAL',SYSDATE-5/1440,SYSDATE+10/1440,'CONFIRMED')",id(p,"reservation"),office,id(p,"space"),PLATE);
     c.commit();p.setProperty("committed","true");save(p);System.out.println("FIXTURE_COMMITTED="+(p.getProperty("wrong_space")==null?4:5));
    } else if(args[0].equals("inspect")){
     try(var s=c.createStatement()){s.execute("SET TRANSACTION READ ONLY");}
     System.out.println("USAGE_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE));
     if(!p.isEmpty()){
      if(p.getProperty("wrong_space")!=null){
       System.out.println("WRONG_SPACE_LINKED_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_SPACE_ID=?",id(p,"wrong_space")));
       String expected=System.getenv("CAMERA_E2E_USAGE_ID");
       if(expected!=null&&!expected.isEmpty()){
        require(expected.matches("[1-9][0-9]*"),"Invalid expected usage");
        System.out.println("TEST_USAGE_UNLINKED="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=? AND EXIT_AT IS NULL AND PARKING_SPACE_ID IS NULL AND PARKING_RESERVATION_ID IS NULL",Long.parseLong(expected),PLATE));
       }
      }
      System.out.println("LINKED_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=? AND PARKING_SPACE_ID=? AND PARKING_RESERVATION_ID=?",PLATE,id(p,"space"),id(p,"reservation")));
      System.out.println("EXITED_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=? AND EXIT_AT IS NOT NULL",PLATE));
      System.out.println("OPEN_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=? AND EXIT_AT IS NULL",PLATE));
      System.out.println("DB_LINK_VERSION="+scalar(c,"SELECT NVL(MAX(LINK_VERSION),-1) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE));
     }c.rollback();
    } else {
     require(!p.isEmpty(),"No manifest; do not delete");
     var ownedUsages=usages(p);
     for(long usage:ownedUsages)require(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=? AND (PARKING_SPACE_ID IS NULL OR PARKING_SPACE_ID=?) AND (PARKING_RESERVATION_ID IS NULL OR PARKING_RESERVATION_ID=?)",usage,PLATE,id(p,"space"),id(p,"reservation"))==1,"Verified usage ownership mismatch; stop cleanup");
     for(long space:spaces(p)){
     require(scalar(c,"SELECT COUNT(*) FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=? AND (RAW_PAYLOAD IS NULL OR (DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_OCCUPANCY\"')=0 AND DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_DECISION\"')=0))",space)==0,"Unexpected detection event on fixture; stop cleanup");
     require(scalar(c,"SELECT COUNT(*) FROM NOTIFICATION WHERE AI_DETECTION_EVENT_ID IN (SELECT AI_DETECTION_EVENT_ID FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=?)",space)==0,"Notification references fixture event; stop cleanup");
     require(scalar(c,"SELECT COUNT(*) FROM SAFETY_INCIDENT WHERE FIRST_AI_DETECTION_EVENT_ID IN (SELECT AI_DETECTION_EVENT_ID FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=?) OR LATEST_AI_DETECTION_EVENT_ID IN (SELECT AI_DETECTION_EVENT_ID FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=?)",space,space)==0,"Safety references fixture event; stop cleanup");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE_HISTORY WHERE PARKING_SPACE_ID=? AND CHANGE_SOURCE_CODE<>'AI'",space)==0,"Unexpected history on fixture; stop cleanup");
     }
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE PARKING_RESERVATION_ID=? AND (VEHICLE_NUMBER<>? OR PARKING_SPACE_ID<>?)",id(p,"reservation"),PLATE,id(p,"space"))==0,"Reservation ownership mismatch");
     for(long space:spaces(p)){
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE WHERE PARKING_SPACE_ID=? AND (PARKING_ZONE_ID<>? OR MEMO<>? OR MEMO IS NULL)",space,id(p,"zone"),p.getProperty("marker"))==0,"Space ownership mismatch");
      long ownedReferences=0;
      for(long usage:ownedUsages)ownedReferences+=scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_SPACE_ID=? AND PARKING_USAGE_ID=?",space,usage);
      require(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_SPACE_ID=?",space)==ownedReferences,"Other usage references fixture");
      require(scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE PARKING_SPACE_ID=? AND PARKING_RESERVATION_ID<>?",space,id(p,"reservation"))==0,"Other reservation references fixture");
     }
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_ZONE WHERE PARKING_ZONE_ID=? AND (PARKING_FLOOR_ID<>? OR ZONE_NAME<>?)",id(p,"zone"),id(p,"floor"),p.getProperty("marker"))==0,"Zone ownership mismatch");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_FLOOR WHERE PARKING_FLOOR_ID=? AND (FLOOR_NO<>999 OR FLOOR_NAME<>?)",id(p,"floor"),p.getProperty("marker"))==0,"Floor ownership mismatch");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE WHERE PARKING_ZONE_ID=?",id(p,"zone"))==spaces(p).size(),"Unexpected space in fixture zone");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_ZONE WHERE PARKING_FLOOR_ID=?",id(p,"floor"))==1,"Unexpected zone in fixture floor");
     int n=0;
     for(long usage:ownedUsages)n+=update(c,"DELETE FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=?",usage,PLATE);
     for(long space:spaces(p)){
     n+=update(c,"DELETE FROM PARKING_SPACE_HISTORY WHERE PARKING_SPACE_ID=? AND CHANGE_SOURCE_CODE='AI'",space);
     n+=update(c,"DELETE FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=? AND (DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_OCCUPANCY\"')>0 OR DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_DECISION\"')>0)",space);
     }
     n+=update(c,"DELETE FROM PARKING_RESERVATION WHERE PARKING_RESERVATION_ID=? AND VEHICLE_NUMBER=? AND PARKING_SPACE_ID=?",id(p,"reservation"),PLATE,id(p,"space"));
     for(long space:spaces(p)){
     n+=update(c,"DELETE FROM PARKING_SPACE WHERE PARKING_SPACE_ID=? AND PARKING_ZONE_ID=? AND MEMO=?",space,id(p,"zone"),p.getProperty("marker"));
     }
     n+=update(c,"DELETE FROM PARKING_ZONE WHERE PARKING_ZONE_ID=? AND PARKING_FLOOR_ID=? AND ZONE_NAME=?",id(p,"zone"),id(p,"floor"),p.getProperty("marker"));
     n+=update(c,"DELETE FROM PARKING_FLOOR WHERE PARKING_FLOOR_ID=? AND FLOOR_NO=999 AND FLOOR_NAME=?",id(p,"floor"),p.getProperty("marker"));
     for(long space:spaces(p))require(scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE WHERE PARKING_SPACE_ID=?",space)==0,"Space cleanup failed");
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE)==id(p,"baseline_usage_count"),"Business usage preservation failed");
     c.commit();System.out.println("OWNED_SYNTHETIC_ROWS_DELETED="+n);
     require(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE VEHICLE_NUMBER=?",PLATE)==id(p,"baseline_usage_count")&&scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE VEHICLE_NUMBER=?",PLATE)==0&&scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE WHERE PARKING_SPACE_ID=?",id(p,"space"))==0&&scalar(c,"SELECT COUNT(*) FROM PARKING_ZONE WHERE PARKING_ZONE_ID=?",id(p,"zone"))==0&&scalar(c,"SELECT COUNT(*) FROM PARKING_FLOOR WHERE PARKING_FLOOR_ID=?",id(p,"floor"))==0,"Cleanup verification failed");
     System.out.println("REMAINING_SYNTHETIC_ROWS=0");System.out.println("PRESERVED_EXISTING_USAGE_COUNT="+p.getProperty("baseline_usage_count"));c.rollback();p.setProperty("cleaned","true");save(p);
    }
   }catch(Exception e){c.rollback();throw e;}
  }
 }
}