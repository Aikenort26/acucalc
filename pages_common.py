"""Helpers compartidos por las páginas."""
import streamlit as st
from core.project import Project


def get_project() -> Project:
    if "project" not in st.session_state:
        st.session_state["project"] = Project()
    return st.session_state["project"]


def show_issues(issues: list[str]) -> None:
    for i in issues:
        st.warning(i)
