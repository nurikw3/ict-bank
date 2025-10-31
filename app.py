import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Конфигурация
API_URL = "http://localhost:8000"

# Настройка страницы
st.set_page_config(page_title="Bank App", page_icon="🏦", layout="wide")

# Инициализация сессии
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None
    st.session_state.username = None

# Стили
st.markdown("""
<style>
    .big-font {
        font-size:30px !important;
        font-weight: bold;
    }
    .success-box {
        padding: 10px;
        background-color: #d4edda;
        border-radius: 5px;
        margin: 10px 0;
    }
    .error-box {
        padding: 10px;
        background-color: #f8d7da;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

def register_user(username, password, full_name):
    try:
        response = requests.post(f"{API_URL}/register", json={
            "username": username,
            "password": password,
            "full_name": full_name
        })
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def login_user(username, password):
    try:
        response = requests.post(f"{API_URL}/login", json={
            "username": username,
            "password": password
        })
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": response.json().get("detail", "Ошибка входа")}
    except Exception as e:
        return {"error": str(e)}

def get_accounts(user_id):
    try:
        response = requests.get(f"{API_URL}/accounts/{user_id}")
        return response.json()
    except Exception as e:
        return {"accounts": []}

def get_transactions(account_id):
    try:
        response = requests.get(f"{API_URL}/transactions/{account_id}")
        return response.json()
    except Exception as e:
        return {"transactions": []}

def create_transaction(account_id, trans_type, amount, description):
    try:
        response = requests.post(f"{API_URL}/transaction", json={
            "account_id": account_id,
            "transaction_type": trans_type,
            "amount": amount,
            "description": description
        })
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def transfer_money(from_account, to_account, amount, description):
    try:
        response = requests.post(f"{API_URL}/transfer", json={
            "from_account": from_account,
            "to_account": to_account,
            "amount": amount,
            "description": description
        })
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Главная логика приложения
def main():
    if not st.session_state.logged_in:
        # Страница входа/регистрации
        st.markdown('<p class="big-font">🏦 Добро пожаловать в Bank App</p>', unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Вход", "Регистрация"])
        
        with tab1:
            st.subheader("Войти в систему")
            login_username = st.text_input("Логин", key="login_user")
            login_password = st.text_input("Пароль", type="password", key="login_pass")
            
            if st.button("Войти", type="primary"):
                if login_username and login_password:
                    result = login_user(login_username, login_password)
                    if "error" in result:
                        st.error(f"❌ {result['error']}")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.user_id = result['user_id']
                        st.session_state.username = result['username']
                        st.rerun()
                else:
                    st.warning("⚠️ Заполните все поля")
        
        with tab2:
            st.subheader("Создать аккаунт")
            reg_username = st.text_input("Логин", key="reg_user")
            reg_password = st.text_input("Пароль", type="password", key="reg_pass")
            reg_fullname = st.text_input("Полное имя", key="reg_name")
            
            if st.button("Зарегистрироваться", type="primary"):
                if reg_username and reg_password and reg_fullname:
                    result = register_user(reg_username, reg_password, reg_fullname)
                    if "error" in result:
                        st.error(f"❌ {result.get('detail', result['error'])}")
                    else:
                        st.success(f"✅ {result['message']}")
                        st.info(f"📋 Ваш номер счета: **{result['account_number']}**")
                        st.balloons()
                else:
                    st.warning("⚠️ Заполните все поля")
    
    else:
        # Главная страница для авторизованного пользователя
        st.sidebar.markdown(f"### 👤 {st.session_state.username}")
        if st.sidebar.button("🚪 Выйти"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()
        
        st.title("🏦 Банковская система")
        
        # Получение счетов
        accounts_data = get_accounts(st.session_state.user_id)
        accounts = accounts_data.get('accounts', [])
        
        if not accounts:
            st.warning("У вас нет счетов")
            return
        
        # Выбор счета
        selected_account = st.selectbox(
            "Выберите счет",
            accounts,
            format_func=lambda x: f"{x['account_number']} - Баланс: {float(x['balance']):.2f} ₸"
        )
        
        # Отображение баланса
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Баланс", f"{float(selected_account['balance']):.2f} ₸")
        with col2:
            st.metric("🔢 Номер счета", selected_account['account_number'])
        with col3:
            st.metric("📅 Тип счета", selected_account['account_type'])
        
        st.divider()
        
        # Операции
        tab1, tab2, tab3 = st.tabs(["💳 Операции", "💸 Перевод", "📊 История"])
        
        with tab1:
            st.subheader("Пополнение и снятие")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("### Пополнить счет")
                deposit_amount = st.number_input("Сумма пополнения", min_value=0.0, step=100.0, key="deposit")
                deposit_desc = st.text_input("Описание", key="deposit_desc")
                if st.button("Пополнить", type="primary"):
                    if deposit_amount > 0:
                        result = create_transaction(
                            selected_account['id'], 
                            'deposit', 
                            deposit_amount, 
                            deposit_desc
                        )
                        if "error" in result:
                            st.error(f"❌ {result['error']}")
                        else:
                            st.success(f"✅ Счет пополнен! Новый баланс: {result['new_balance']:.2f} ₸")
                            st.rerun()
                    else:
                        st.warning("⚠️ Введите сумму")
            
            with col2:
                st.write("### Снять со счета")
                withdraw_amount = st.number_input("Сумма снятия", min_value=0.0, step=100.0, key="withdraw")
                withdraw_desc = st.text_input("Описание", key="withdraw_desc")
                if st.button("Снять", type="primary"):
                    if withdraw_amount > 0:
                        result = create_transaction(
                            selected_account['id'], 
                            'withdrawal', 
                            withdraw_amount, 
                            withdraw_desc
                        )
                        if "error" in result:
                            st.error(f"❌ {result.get('detail', result['error'])}")
                        else:
                            st.success(f"✅ Снятие выполнено! Новый баланс: {result['new_balance']:.2f} ₸")
                            st.rerun()
                    else:
                        st.warning("⚠️ Введите сумму")
        
        with tab2:
            st.subheader("Перевод средств")
            to_account = st.text_input("Номер счета получателя")
            transfer_amount = st.number_input("Сумма перевода", min_value=0.0, step=100.0)
            transfer_desc = st.text_input("Описание перевода")
            
            if st.button("Перевести", type="primary"):
                if to_account and transfer_amount > 0:
                    result = transfer_money(
                        selected_account['account_number'],
                        to_account,
                        transfer_amount,
                        transfer_desc
                    )
                    if "error" in result:
                        st.error(f"❌ {result.get('detail', result['error'])}")
                    else:
                        st.success(f"✅ {result['message']}")
                        st.balloons()
                        st.rerun()
                else:
                    st.warning("⚠️ Заполните все поля")
        
        with tab3:
            st.subheader("История транзакций")
            trans_data = get_transactions(selected_account['id'])
            transactions = trans_data.get('transactions', [])
            
            if transactions:
                df = pd.DataFrame(transactions)
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
                df['amount'] = df['amount'].astype(float).round(2)
                
                # Форматирование типов транзакций
                type_map = {
                    'deposit': '📥 Пополнение',
                    'withdrawal': '📤 Снятие',
                    'transfer_in': '⬅️ Входящий',
                    'transfer_out': '➡️ Исходящий'
                }
                df['transaction_type'] = df['transaction_type'].map(type_map)
                
                st.dataframe(
                    df[['created_at', 'transaction_type', 'amount', 'description']],
                    column_config={
                        "created_at": "Дата",
                        "transaction_type": "Тип",
                        "amount": st.column_config.NumberColumn("Сумма (₸)", format="%.2f"),
                        "description": "Описание"
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("📭 Нет транзакций")

if __name__ == "__main__":
    main()