package kr.co.alpharking.security;
import java.sql.Date;
import java.util.Collection;
import java.util.List;

import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.SequenceGenerator;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "OFFICE")
//Spring Security가 관리 하는 Entity : UserDetails 인터페이스를 구현하고 , 추상메서드를 재정의 해놔야
//시큐리티가 추상메서드를 가져가서 인증관련 호출 
public class Office implements UserDetails {
	@Id
	private Long office_id;
	private Long company_id;
	private Long floor_no;
	private String office_number;
	private String email;
	private String phone;
	private String verification_code;
	private String status_code;
	private Date created_at;
	private Date updated_at;
	private Date withdrawn_at;
	
    @Column(unique = true, nullable = false, name = "login_id") 
    private String username; // 아이디 값을 이메일로 넣어서 사영
    @Column(name = "password_hash")
    private String password; // 비밀번호
    
//    //롤을 check제약조건으로 지정 해놓는다.
//    @Enumerated(EnumType.STRING)
//    @Column(nullable = false, columnDefinition = "VARCHAR(10) CHECK (ROLE IN ('ADMIN', 'OFFICE'))")
//    private Role role;
    
    //생성자 
	public Office(Long floor_no, String office_number, String login_id, String password_hash, Role role) {
		this.floor_no = floor_no;
		this.office_number = office_number;
		this.username = login_id;
		this.password = password_hash;
//		this.role = role;
	}
	
//	//Role에서 권한(ADMIN, USER)을 지정했는데 그 권한을 읽어오기 위한 객체(GrantedAuthority) SimpleGrantedAuthority로 반환 
	@Override
	public Collection<? extends GrantedAuthority> getAuthorities() {
		return List.of(new SimpleGrantedAuthority("OFFICE"));
	}
	// 사용자의 아이디를 반환, 사용자를 식별 할 때 사용하는 메서드를 만들자.
	public String getUsername() {
		return this.username;
	}
    public String getPassword() {
        return this.password;
    }
    //나머지도 재정의 한다.
   // 계정이 만료되었는지 여부를 반환 하는데 , true를 반환해서 계정이 만료 안됨을 반환하도록 설정했다.
	@Override
	public boolean isAccountNonExpired() {
		return true;
	}
	//계정이 잠김 유무, true이면 계정 안잠김
	@Override
	public boolean isAccountNonLocked() {
		return true;
	}
	// 자격 증명(비밀번호)이 만료되었는지 여부를 반환. 마찬가지로 만료 안됨
	@Override
	public boolean isCredentialsNonExpired() {
		return true;
	}
	// 계정이 활성화되어 있는지 여부를 반환, 계정이 활성화되었음을 반환
	@Override
	public boolean isEnabled() {
		return true;
	}

    
}






