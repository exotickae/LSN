import streamlit as st

st.set_page_config(page_title="Light-Speed Node", layout="centered")

st.title("💡 Light-Speed Node - Local AI Chat")

user_input = st.text_input("You:", key="input")

if user_input:
    st.markdown(f"**AI:** You said _{user_input}_ — but the brain isn't wired up yet.")
