package kr.co.alpharking.entity.auditlog;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "AUDIT_LOG")
public class AuditlogEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "AUDIT_LOG_ID")
    private Long auditlogid;

    @Column(name = "ACTOR_TYPE_CODE", nullable = false, length = 20)
    private String actortypecode;

    @Column(name = "ACTOR_ID", nullable = false)
    private Long actorid;

    @Column(name = "ACTION_TYPE_CODE", nullable = false, length = 50)
    private String actiontypecode;

    @Column(name = "TARGET_TABLE", nullable = false, length = 100)
    private String targettable;

    @Column(name = "TARGET_ID")
    private Long targetid;

    @Column(name = "BEFORE_DATA", columnDefinition = "CLOB")
    private String beforedata;

    @Column(name = "AFTER_DATA", columnDefinition = "CLOB")
    private String afterdata;

    @Column(name = "CHANGE_REASON", length = 4000)
    private String changereason;

    @Column(name = "OCCURRED_AT", nullable = false, updatable = false)
    private LocalDateTime createdat;

    public Long getAuditlogid() {
        return auditlogid;
    }

    public void setAuditlogid(Long auditlogid) {
        this.auditlogid = auditlogid;
    }

    public String getActortypecode() {
        return actortypecode;
    }

    public void setActortypecode(String actortypecode) {
        this.actortypecode = actortypecode;
    }

    public Long getActorid() {
        return actorid;
    }

    public void setActorid(Long actorid) {
        this.actorid = actorid;
    }

    public String getActiontypecode() {
        return actiontypecode;
    }

    public void setActiontypecode(String actiontypecode) {
        this.actiontypecode = actiontypecode;
    }

    public String getTargettable() {
        return targettable;
    }

    public void setTargettable(String targettable) {
        this.targettable = targettable;
    }

    public Long getTargetid() {
        return targetid;
    }

    public void setTargetid(Long targetid) {
        this.targetid = targetid;
    }

    public String getBeforedata() {
        return beforedata;
    }

    public void setBeforedata(String beforedata) {
        this.beforedata = beforedata;
    }

    public String getAfterdata() {
        return afterdata;
    }

    public void setAfterdata(String afterdata) {
        this.afterdata = afterdata;
    }

    public String getChangereason() {
        return changereason;
    }

    public void setChangereason(String changereason) {
        this.changereason = changereason;
    }

    public LocalDateTime getCreatedat() {
        return createdat;
    }

    public void setCreatedat(LocalDateTime createdat) {
        this.createdat = createdat;
    }
}
