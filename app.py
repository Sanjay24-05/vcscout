"""
VC Scout - Autonomous Market Validator with Strategic Pivoting

A multi-agent system that validates startup ideas through deep market research,
competitor analysis, and autonomous pivoting for non-viable ideas.
"""

import asyncio
import streamlit as st

from src.db.connection import init_db
from src.runner import create_and_run_job
from src.ui import (
    ensure_db_session,
    format_timestamp,
    get_job_details,
    get_or_create_session_token,
    get_session_jobs,
    render_status_badge,
    render_thought_trace,
)

# Page configuration
st.set_page_config(
    page_title="VC Scout - Market Validator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #6B7280;
        margin-bottom: 2rem;
    }
    .stExpander {
        border: 1px solid #E5E7EB;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


def run_async(coro):
    """Run an async coroutine in Streamlit"""
    # Reset DB engine to avoid event loop conflicts
    from src.db.connection import _reset_engine
    _reset_engine()
    
    return asyncio.run(coro)


def main():
    """Main Streamlit application"""
    
    # Initialize database on first run
    if "db_initialized" not in st.session_state:
        with st.spinner("Initializing database..."):
            run_async(init_db())
        st.session_state.db_initialized = True
    
    # Get or create session
    session_token = get_or_create_session_token()
    
    # Sidebar - History
    with st.sidebar:
        st.markdown("## 📜 Analysis History")
        
        # Fetch past jobs
        jobs = run_async(get_session_jobs(session_token))
        
        if not jobs:
            st.info("No previous analyses. Submit your first idea!")
        else:
            for job in jobs:
                col1, col2 = st.columns([3, 1])
                with col1:
                    if st.button(
                        f"{job['original_idea'][:30]}...",
                        key=f"job_{job['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.selected_job_id = job["id"]
                        st.session_state.show_results = True
                with col2:
                    st.markdown(render_status_badge(job["status"]))
        
        st.markdown("---")
        st.markdown(f"Session: `{session_token[:8]}...`")
    
    # Main content
    st.markdown('<p class="main-header">🔍 VC Scout</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Autonomous Market Validator with Strategic Pivoting</p>',
        unsafe_allow_html=True,
    )
    
    # Check if viewing a specific job
    if st.session_state.get("show_results") and st.session_state.get("selected_job_id"):
        job_id = st.session_state.selected_job_id
        job_details = run_async(get_job_details(job_id))
        
        if job_details:
            # Back button
            if st.button("← Back to New Analysis"):
                st.session_state.show_results = False
                st.session_state.selected_job_id = None
                st.rerun()
            
            st.markdown("---")
            
            # Job header
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"**Original Idea:** {job_details['original_idea']}")
            with col2:
                st.markdown(f"**Status:** {render_status_badge(job_details['status'])}")
            with col3:
                st.markdown(f"**Pivots:** {job_details['pivot_attempts']}")
            
            # Error display
            if job_details.get("error_message"):
                st.error(f"Error: {job_details['error_message']}")
            
            # Thought trace
            render_thought_trace(job_details)
            
            # Final report
            if job_details.get("final_report"):
                st.markdown("---")
                st.markdown(job_details["final_report"])
            elif job_details["status"] == "running":
                st.info("Analysis in progress... Refresh to see updates.")
            elif job_details["status"] == "pending":
                st.info("Analysis queued...")
        else:
            st.error("Job not found")
            st.session_state.show_results = False
    
    else:
        # New analysis form
        st.markdown("### 💡 Submit Your Startup Idea")
        
        with st.form("idea_form"):
            idea = st.text_area(
                "Describe your startup idea",
                placeholder="e.g., An AI-powered legal document assistant for small businesses...",
                height=100,
            )
            
            col1, col2 = st.columns([1, 3])
            with col1:
                submitted = st.form_submit_button("🚀 Analyze", use_container_width=True)
        
        if submitted and idea.strip():
            # Ensure we have a DB session
            session_id = run_async(ensure_db_session(session_token))
            
            # Progress display
            progress_container = st.empty()
            status_text = st.empty()
            
            def update_progress(message: str):
                status_text.markdown(f"**Status:** {message}")
            
            with st.spinner("Running autonomous market analysis..."):
                result = run_async(create_and_run_job(
                    session_id=session_id,
                    idea=idea.strip(),
                    progress_callback=update_progress,
                ))
            
            if result["status"] == "completed":
                st.success("✅ Analysis complete!")
                st.session_state.selected_job_id = result["job_id"]
                st.session_state.show_results = True
                st.rerun()
            else:
                st.error(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")
        
        elif submitted:
            st.warning("Please enter a startup idea to analyze.")
        
        # How it works
        st.markdown("---")
        st.markdown("### 🔄 How It Works")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            **1. Market Research** 🔍
            
            Searches for TAM, growth trends, and target demographics.
            """)
        
        with col2:
            st.markdown("""
            **2. Competitor Analysis** 📊
            
            Scrapes and analyzes top competitors' features and pricing.
            """)
        
        with col3:
            st.markdown("""
            **3. Critical Evaluation** 😈
            
            Devil's Advocate scores viability and suggests pivots.
            """)
        
        with col4:
            st.markdown("""
            **4. Final Report** ✍️
            
            Investment Memo or Market Reality Report with full findings.
            """)
        
        st.markdown("---")
        st.markdown("""
        **🔄 Autonomous Pivoting:** If your idea scores ≤5/10, the system automatically 
        suggests and researches pivot opportunities (up to 3 attempts) before generating 
        a final report.
        """)


if __name__ == "__main__":
    main()
