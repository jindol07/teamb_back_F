import java.sql.*;
import java.nio.file.*;
import java.util.*;

/** 기존 지하 3층 구획은 생성·삭제하지 않고 이번 예약만 소유 ID로 관리합니다. */
public class DeployedSpaceFixture {
 static long scalar(Connection c,String sql,Object...args)throws Exception{return CameraE2EFixture.scalar(c,sql,args);}
 static int update(Connection c,String sql,Object...args)throws Exception{return CameraE2EFixture.update(c,sql,args);}
 static void check(boolean ok,String message){if(!ok)throw new IllegalStateException(message);}
 static void save(Path file,Properties p)throws Exception{try(var out=Files.newOutputStream(file)){p.store(out,"Owned reservation on existing deployed spaces");}}
 public static void main(String[] args)throws Exception{
  check(args.length==1&&Set.of("check","prepare","inspect","cancel","close-usage","restore-spaces").contains(args[0]),"Explicit mode required");
  var file=Path.of(System.getenv("DEPLOYED_DEMO_MANIFEST"));
  String plate="91소6408";String target="jdbc:oracle:thin:@15.165.205.246:1521:xe";
  check(target.equals(System.getenv("DB_URL")),"Unexpected DB target");
  var cfg=new Properties();try(var r=Files.newBufferedReader(Path.of("apcms_a/src/main/resources/application.properties"))){cfg.load(r);}
  DriverManager.setLoginTimeout(8);
  try(var c=DriverManager.getConnection(target,CameraE2EFixture.resolve(cfg.getProperty("spring.datasource.username")),CameraE2EFixture.resolve(cfg.getProperty("spring.datasource.password")))){
   c.setAutoCommit(false);var p=new Properties();if(Files.exists(file))try(var in=Files.newInputStream(file)){p.load(in);}
   try{
    if(args[0].equals("prepare")||args[0].equals("check")){
     check(p.isEmpty(),"Existing manifest requires review");
     check(scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE s JOIN PARKING_ZONE z ON z.PARKING_ZONE_ID=s.PARKING_ZONE_ID JOIN PARKING_FLOOR f ON f.PARKING_FLOOR_ID=z.PARKING_FLOOR_ID WHERE f.FLOOR_NO=3 AND z.ZONE_CODE='A' AND ((s.SPACE_NUMBER='01' AND s.PARKING_SPACE_ID=46) OR (s.SPACE_NUMBER='02' AND s.PARKING_SPACE_ID=47) OR (s.SPACE_NUMBER='03' AND s.PARKING_SPACE_ID=48) OR (s.SPACE_NUMBER='04' AND s.PARKING_SPACE_ID=49)) AND s.SPACE_STATUS_CODE IN ('AVAILABLE','EMPTY')")==4,"Spaces unavailable or mapping changed");
     if(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE EXIT_AT IS NULL AND (VEHICLE_NUMBER=? OR PARKING_SPACE_ID IN (46,47,48,49))",plate)>0){
      var ids=new StringJoiner(",");try(var st=c.prepareStatement("SELECT PARKING_USAGE_ID FROM PARKING_USAGE WHERE EXIT_AT IS NULL AND (VEHICLE_NUMBER=? OR PARKING_SPACE_ID IN (46,47,48,49)) ORDER BY PARKING_USAGE_ID")){st.setString(1,plate);try(var rs=st.executeQuery()){while(rs.next())ids.add(Long.toString(rs.getLong(1)));}}
      System.err.println("ACTIVE_USAGE_IDS="+ids);check(false,"Active usage exists");
     }
     check(scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE STATUS_CODE='CONFIRMED' AND CANCELLED_AT IS NULL AND (PARKING_SPACE_ID IN (46,47,48,49) OR VEHICLE_NUMBER=?) AND RESERVATION_END_AT>=LEAST(CAST(SYSDATE AS TIMESTAMP),CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS TIMESTAMP)) AND RESERVATION_START_AT<=GREATEST(CAST(SYSDATE AS TIMESTAMP),CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS TIMESTAMP))+INTERVAL '45' MINUTE",plate)==0,"Reservation conflict");
     if(args[0].equals("check")){c.rollback();System.out.println("EXISTING_SPACES_READY=1");return;}
     long vehicleCount=scalar(c,"SELECT COUNT(*) FROM VEHICLE WHERE VEHICLE_NUMBER=?",plate);check(vehicleCount<=1,"Duplicate vehicle");
     String marker="AI_SITE_TEST_"+UUID.randomUUID().toString().substring(0,8);p.setProperty("marker",marker);
     for(long space:new long[]{46,47,48,49})try(var st=c.prepareStatement("SELECT SPACE_STATUS_CODE FROM PARKING_SPACE WHERE PARKING_SPACE_ID=?")){
      st.setLong(1,space);try(var rs=st.executeQuery()){check(rs.next(),"Missing space");p.setProperty("baseline_status_"+space,rs.getString(1));}
     }
     long office;
     if(vehicleCount==0){
      office=1;check(scalar(c,"SELECT COUNT(*) FROM OFFICE WHERE OFFICE_ID=1")==1,"Office reference missing");
      long vehicle=scalar(c,"SELECT SEQ_VEHICLE.NEXTVAL FROM DUAL");p.setProperty("created_vehicle",Long.toString(vehicle));
      p.setProperty("vehicle_office",Long.toString(office));save(file,p);
      update(c,"INSERT INTO VEHICLE(VEHICLE_ID,OFFICE_ID,VEHICLE_NUMBER,VEHICLE_TYPE_CODE,REGISTRATION_TYPE_CODE,REGISTRATION_STATUS_CODE,OWNER_NAME,REGISTERED_AT) VALUES(?,?,?,'PERSONAL','INITIAL','REGISTERED',?,SYSDATE)",vehicle,office,plate,marker);
     }else{office=scalar(c,"SELECT OFFICE_ID FROM VEHICLE WHERE VEHICLE_NUMBER=?",plate);}
     if("1".equals(System.getenv("DEPLOYED_DEMO_NO_RESERVATION"))){
      p.setProperty("reservation_mode","none");p.setProperty("office",Long.toString(office));p.setProperty("plate",plate);
      c.commit();p.setProperty("committed","true");save(file,p);System.out.println("RESERVATION_MODE=NONE");return;
     }
     long reservation=scalar(c,"SELECT SEQ_PARKING_RESERVATION.NEXTVAL FROM DUAL");
     p.setProperty("reservation",Long.toString(reservation));p.setProperty("office",Long.toString(office));p.setProperty("plate",plate);save(file,p);
     // DB와 Boot의 기존 시간대 차이를 포괄하며 종료 시 이 예약만 취소합니다.
     update(c,"INSERT INTO PARKING_RESERVATION(PARKING_RESERVATION_ID,OFFICE_ID,PARKING_SPACE_ID,VEHICLE_NUMBER,RESERVATION_TYPE_CODE,RESERVATION_START_AT,RESERVATION_END_AT,STATUS_CODE) VALUES(?,?,46,?,'NORMAL',LEAST(CAST(SYSDATE AS TIMESTAMP),CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS TIMESTAMP))-INTERVAL '5' MINUTE,GREATEST(CAST(SYSDATE AS TIMESTAMP),CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS TIMESTAMP))+INTERVAL '45' MINUTE,'CONFIRMED')",reservation,office,plate);
     c.commit();p.setProperty("committed","true");save(file,p);System.out.println("RESERVATION_ID="+reservation+"\nSPACE_CODE=3F-A01");
    }else{
     check(p.getProperty("committed","").equals("true"),"No committed owned reservation");
     check(p.getProperty("marker","").matches("AI_SITE_TEST_[0-9a-f]{8}")&&plate.equals(p.getProperty("plate")),"Unknown test ownership");
     boolean reserved=p.containsKey("reservation");
     long reservation=reserved?Long.parseLong(p.getProperty("reservation")):0;long office=Long.parseLong(p.getProperty("office"));
     if(reserved)check(scalar(c,"SELECT COUNT(*) FROM PARKING_RESERVATION WHERE PARKING_RESERVATION_ID=? AND OFFICE_ID=? AND PARKING_SPACE_ID=46 AND VEHICLE_NUMBER=?",reservation,office,plate)==1,"Reservation ownership mismatch");
     else check("none".equals(p.getProperty("reservation_mode")),"Missing reservation mode");
     if(args[0].equals("close-usage")){
      String raw=System.getenv("DEPLOYED_DEMO_USAGE_ID");check(raw!=null&&raw.matches("[1-9][0-9]*"),"Explicit usage required");
      long usage=Long.parseLong(raw);
      check(scalar(c,"SELECT PARKING_USAGE_ID FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? FOR UPDATE NOWAIT",usage)==usage,"Usage lock mismatch");
      var at=java.time.OffsetDateTime.parse(System.getenv("DEPLOYED_DEMO_ENTRY_AT")).atZoneSameInstant(java.time.ZoneId.of("Asia/Seoul")).toLocalDateTime().withNano(0);
      String stamp=at.format(java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
      check(scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=? AND OFFICE_ID=? AND TO_CHAR(ENTRY_AT,'YYYY-MM-DD HH24:MI:SS')=? AND (PARKING_SPACE_ID IS NULL OR PARKING_SPACE_ID IN (46,47,48,49)) AND (PARKING_RESERVATION_ID IS NULL OR PARKING_RESERVATION_ID=?)",usage,plate,office,stamp,reservation)==1,"Usage ownership mismatch");
      int closed=update(c,"UPDATE PARKING_USAGE SET EXIT_AT=GREATEST(ENTRY_AT,CAST(SYSTIMESTAMP AT TIME ZONE 'Asia/Seoul' AS TIMESTAMP)) WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=? AND EXIT_AT IS NULL",usage,plate);
      c.commit();System.out.println("OWNED_USAGE_CLOSED="+closed);System.out.println("USAGE_ID="+usage);
     }else if(args[0].equals("restore-spaces")){
      var records=new Properties();try(var in=Files.newInputStream(file.resolveSibling("owned_occupancy.properties"))){records.load(in);}
      int restored=0,skipped=0;
      for(long space:new long[]{46,47,48,49}){
       String event=records.getProperty("event_"+space),raw=records.getProperty("id_"+space),baseline=p.getProperty("baseline_status_"+space);
       if(event==null||raw==null||baseline==null)continue;
       check(scalar(c,"SELECT PARKING_SPACE_ID FROM PARKING_SPACE WHERE PARKING_SPACE_ID=? FOR UPDATE NOWAIT",space)==space,"Space lock mismatch");
       check(event.matches("[0-9a-f-]{36}")&&raw.matches("[1-9][0-9]*")&&Set.of("AVAILABLE","EMPTY").contains(baseline),"Invalid occupancy ownership");long id=Long.parseLong(raw);
       check(scalar(c,"SELECT COUNT(*) FROM AI_DETECTION_EVENT WHERE AI_DETECTION_EVENT_ID=? AND PARKING_SPACE_ID=? AND DBMS_LOB.INSTR(RAW_PAYLOAD,?)>0",id,space,"\"event_id\":\""+event+"\"")==1,"Occupancy ownership mismatch");
       if(scalar(c,"SELECT NVL(MAX(AI_DETECTION_EVENT_ID),0) FROM AI_DETECTION_EVENT WHERE PARKING_SPACE_ID=? AND DBMS_LOB.INSTR(RAW_PAYLOAD,'\"event_type\":\"PARKING_OCCUPANCY\"')>0",space)!=id
          ||scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_SPACE_ID=? AND EXIT_AT IS NULL",space)>0
          ||scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE_HISTORY WHERE PARKING_SPACE_ID=? AND CHANGE_SOURCE_CODE='ADMIN' AND VALID_FROM>=(SELECT CREATED_AT FROM AI_DETECTION_EVENT WHERE AI_DETECTION_EVENT_ID=?)",space,id)>0){skipped++;continue;}
       if(scalar(c,"SELECT COUNT(*) FROM PARKING_SPACE WHERE PARKING_SPACE_ID=? AND SPACE_STATUS_CODE IN ('AVAILABLE','EMPTY','OCCUPIED') AND SPACE_STATUS_CODE<>?",space,baseline)==0)continue;
       update(c,"UPDATE PARKING_SPACE_HISTORY SET VALID_TO=SYSDATE WHERE PARKING_SPACE_ID=? AND VALID_TO IS NULL",space);
       restored+=update(c,"UPDATE PARKING_SPACE SET SPACE_STATUS_CODE=?,UPDATED_AT=SYSDATE WHERE PARKING_SPACE_ID=?",baseline,space);
       update(c,"INSERT INTO PARKING_SPACE_HISTORY(PARKING_SPACE_HISTORY_ID,PARKING_SPACE_ID,PARKING_ZONE_ID,SPACE_NUMBER,SPACE_TYPE_CODE,SPACE_STATUS_CODE,X_POSITION,Y_POSITION,MEMO,VALID_FROM,CHANGE_SOURCE_CODE,CHANGE_REASON,AI_DETECTION_EVENT_ID) SELECT SEQ_PARKING_SPACE_HISTORY.NEXTVAL,PARKING_SPACE_ID,PARKING_ZONE_ID,SPACE_NUMBER,SPACE_TYPE_CODE,SPACE_STATUS_CODE,X_POSITION,Y_POSITION,MEMO,SYSDATE,'AI','TEST_ABORTED_CLEANUP',? FROM PARKING_SPACE WHERE PARKING_SPACE_ID=?",id,space);
      }
      c.commit();System.out.println("OWNED_SPACES_RESTORED="+restored);System.out.println("CHANGED_SPACES_PRESERVED="+skipped);
     }else if(args[0].equals("cancel")){
      if(!reserved){c.rollback();System.out.println("NO_RESERVATION_CREATED=1");return;}
      update(c,"UPDATE PARKING_RESERVATION SET STATUS_CODE='CANCELLED',CANCELLED_AT=SYSDATE WHERE PARKING_RESERVATION_ID=? AND OFFICE_ID=? AND PARKING_SPACE_ID=46 AND VEHICLE_NUMBER=? AND CANCELLED_AT IS NULL",reservation,office,plate);
      c.commit();p.setProperty("cancelled","true");save(file,p);System.out.println("OWNED_RESERVATION_CANCELLED="+reservation);
     }else{
      String raw=System.getenv("DEPLOYED_DEMO_USAGE_ID");check(raw!=null&&raw.matches("[1-9][0-9]*"),"Explicit usage required");long usage=Long.parseLong(raw);
      System.out.println("USAGE_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=?",usage,plate));
      System.out.println("LINKED_SPACE_ID="+scalar(c,"SELECT NVL(MAX(PARKING_SPACE_ID),0) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=?",usage,plate));
      System.out.println("LINKED_RESERVATION_ID="+scalar(c,"SELECT NVL(MAX(PARKING_RESERVATION_ID),0) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=?",usage,plate));
      System.out.println("UNLINKED_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=? AND EXIT_AT IS NULL AND PARKING_SPACE_ID IS NULL AND PARKING_RESERVATION_ID IS NULL",usage,plate));
      System.out.println("MATCHED_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=? AND PARKING_SPACE_ID=46 AND PARKING_RESERVATION_ID=?",usage,plate,reservation));
      System.out.println("EXITED_ROWS="+scalar(c,"SELECT COUNT(*) FROM PARKING_USAGE WHERE PARKING_USAGE_ID=? AND VEHICLE_NUMBER=? AND EXIT_AT IS NOT NULL",usage,plate));
      c.rollback();
     }
    }
   }catch(Exception e){c.rollback();throw e;}
  }
 }
}
