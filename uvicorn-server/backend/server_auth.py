from ldap3 import Server, Connection, ALL, NTLM
from config import (
    LDAP_SERVER, DOMAIN, SERVICE_USER, SERVICE_PASSWORD, 
    LDAP_SEARCH_BASE, GROUP_DN, SYSMASTER_USERNAME, SYSMASTER_PASSWORD
)

def check_ldap_user(username: str, password: str) -> bool:
    """
    Проверяет пользователя через LDAP домен.
    Пользователь должен существовать и быть в группе GROUP_DN.
    
    Args:
        username: Имя пользователя (без домена)
        password: Пароль пользователя
        
    Returns:
        True если авторизация прошла успешно, False иначе
    """
    user_principal = f'{username}@{DOMAIN.lower()}.internal'
    
    try:
        # Подключение к серверу сервисной учёткой
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

        # Проверяем правильность пароля
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
        print(f"Ошибка при LDAP-проверке пользователя: {e}")
        return False
    finally:
        if 'service_conn' in locals():
            service_conn.unbind()
        if 'user_conn' in locals():
            user_conn.unbind()


def check_local_user(username: str, password: str) -> bool:
    """
    Проверяет локального пользователя sysmaster.
    
    Args:
        username: Имя пользователя
        password: Пароль пользователя
        
    Returns:
        True если учетные данные корректны, False иначе
    """
    return username == SYSMASTER_USERNAME and password == SYSMASTER_PASSWORD


def authenticate_user(username: str, password: str, auth_type: str = 'ldap') -> tuple[bool, str]:
    """
    Функция для аутентификации пользователя.
    
    Args:
        username: Имя пользователя
        password: Пароль пользователя
        auth_type: Тип аутентификации ('ldap' или 'local')
        
    Returns:
        Кортеж (успех, user_dn)
    """
    if auth_type == 'ldap':
        if check_ldap_user(username, password):
            user_dn = f"{username}@{DOMAIN.lower()}.internal"
            return True, user_dn
    elif auth_type == 'local':
        if check_local_user(username, password):
            user_dn = f"{username}@local"
            return True, user_dn
    
    return False, ""
