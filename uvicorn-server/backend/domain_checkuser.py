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
        # Подключение к серверу сервисной учёткой, чтобы найти DN пользователя и его группы
        server = Server(LDAP_SERVER, get_info=ALL)
        service_conn = Connection(
            server,
            user=SERVICE_USER,
            password=SERVICE_PASSWORD,
            authentication='SIMPLE',
            auto_bind=True
        )

        service_conn.search(
            search_base=LDAP_SEARCH_BASE,
            search_filter=f'(userPrincipalName={user_principal})',
            attributes=['distinguishedName', 'memberOf']
        )

        if not service_conn.entries:
            return False

        user_entry = service_conn.entries[0]
        groups = user_entry.memberOf.values if 'memberOf' in user_entry else []
        if GROUP_DN not in groups:
            return False

        # Проверяем правильность пароля, пробуя привязаться как сам пользователь
        user_conn = Connection(
            server,
            user=user_principal,
            password=password,
            authentication='SIMPLE',
            auto_bind=True
        )
        user_conn.unbind()
        return True

    except Exception as e:
        print(f"Ошибка при проверке пользователя: {e}")
        return False
    finally:
        if 'service_conn' in locals():
            service_conn.unbind()
        if 'user_conn' in locals():
            user_conn.unbind()