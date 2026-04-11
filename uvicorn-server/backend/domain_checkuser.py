from ldap3 import Server, Connection, ALL, NTLM
from config import LDAP_SERVER, DOMAIN, SERVICE_USER, SERVICE_PASSWORD, LDAP_SEARCH_BASE, GROUP_DN

def check_user_in_group(username: str, password: str) -> bool:
    """
    Проверяет, существует ли пользователь в домене и состоит ли он в группе GROUP_DN.
    
    Args:
        username: Имя пользователя (без домена)
        password: Пароль пользователя
        
    Returns:
        True если пользователь найден и в группе, False иначе
    """
    user_principal = f'{username}@{DOMAIN.lower()}.internal'
    
    try:
        # Подключение к серверу
        server = Server(LDAP_SERVER, get_info=ALL)
        conn = Connection(
            server,
            user=SERVICE_USER,
            password=SERVICE_PASSWORD,
            authentication='SIMPLE',
            auto_bind=True
        )
        
        # Ищем пользователя
        conn.search(
            search_base=LDAP_SEARCH_BASE,
            search_filter=f'(userPrincipalName={user_principal})',
            attributes=['memberOf']
        )
        
        if not conn.entries:
            return False
        
        user_entry = conn.entries[0]
        
        # Проверяем членство в группе
        groups = user_entry.memberOf.values if 'memberOf' in user_entry else []
        
        return GROUP_DN in groups
        
    except Exception as e:
        print(f"Ошибка при проверке пользователя: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.unbind()