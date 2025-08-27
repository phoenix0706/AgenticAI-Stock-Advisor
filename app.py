import os
import yfinance as yf
import streamlit as st
from agno.agent import Agent
from agno.models.google import Gemini
import plotly.graph_objects as go
from dotenv import load_dotenv
# Load environment variables from .env
load_dotenv()

# Read the API key from environment
google_api_key = os.getenv("GOOGLE_API_KEY")
if google_api_key:
    os.environ["GOOGLE_API_KEY"] = google_api_key
else:
    st.error("Google API Key is missing. Please set it in your .env file.")


# Function to fetch and compare stock data
def fetch_stock_performance(symbols):
    performance = {}
    for symbol in symbols:
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="6mo")
            if hist.empty:
                print(f"No data found for {symbol}, skipping it.")
                continue
            performance[symbol] = hist['Close'].pct_change().sum()
        except Exception as e:
            print(f"Could not retrieve data for {symbol}. Reason: {str(e)}")
            continue
    return performance

# Market Performance Agent
market_insight_agent = Agent(
    model=Gemini(id="gemini-2.0-flash-exp"),
    description="Provides insight on stock performance over a 6-month window.",
    instructions=[
        "Analyze historical stock performance.",
        "Use percent changes over 6 months.",
        "Rank by overall growth."
    ],
    show_tool_calls=True,
    markdown=True
)

def generate_market_insights(symbols):
    perf_data = fetch_stock_performance(symbols)
    if not perf_data:
        return "No valid stock data found for the given symbols."
    insight = market_insight_agent.run(f"Analyze these stock performances: {perf_data}")
    return insight.content

# Company Info + News
def extract_company_profile(symbol):
    stock = yf.Ticker(symbol)
    return {
        "name": stock.info.get("longName", "N/A"),
        "sector": stock.info.get("sector", "N/A"),
        "market_cap": stock.info.get("marketCap", "N/A"),
        "summary": stock.info.get("longBusinessSummary", "N/A"),
    }

def extract_company_news(symbol):
    stock = yf.Ticker(symbol)
    return stock.news[:5]

company_insight_agent = Agent(
    model=Gemini(id="gemini-2.0-flash-exp"),
    description="Summarizes company profile, business area, and latest updates.",
    instructions=[
        "Get company profile and business summary.",
        "Summarize top news articles for investors.",
        "Include sector and market cap in context."
    ],
    markdown=True
)

def compile_company_insight(symbol):
    profile = extract_company_profile(symbol)
    news = extract_company_news(symbol)
    response = company_insight_agent.run(
        f"Company: {profile['name']} | Sector: {profile['sector']}\n"
        f"Market Cap: {profile['market_cap']}\n"
        f"Summary: {profile['summary']}\n"
        f"Top News: {news}"
    )
    return response.content

# Stock Strategy Agent
strategy_agent = Agent(
    model=Gemini(id="gemini-2.0-flash-exp"),
    description="Analyzes investment strategy and picks top stocks.",
    instructions=[
        "Identify top stocks based on data and market signals.",
        "Weigh growth, risk, and recent trends.",
        "Provide actionable stock picks."
    ],
    markdown=True
)

def recommend_top_stocks(symbols):
    market_overview = generate_market_insights(symbols)
    company_profiles = {symbol: compile_company_insight(symbol) for symbol in symbols}
    recommendation = strategy_agent.run(
        f"Market Overview: {market_overview},\nCompany Details: {company_profiles}\n"
        f"Which stocks are best suited for investment?"
    )
    return recommendation.content

# Final Aggregator Agent
insight_compiler = Agent(
    model=Gemini(id="gemini-2.0-flash-exp"),
    description="Combines performance, company info, and strategy into a report.",
    instructions=[
        "Summarize all data in an easy-to-read investment report.",
        "Provide performance + fundamentals per stock.",
        "Rank all symbols based on buy potential."
    ],
    markdown=True
)

def build_investment_summary(symbols):
    market = generate_market_insights(symbols)
    company_details = [compile_company_insight(sym) for sym in symbols]
    picks = recommend_top_stocks(symbols)

    final_output = insight_compiler.run(
        f"Performance Data:\n{market}\n\n"
        f"Company Insights:\n{company_details}\n\n"
        f"Investment Picks:\n{picks}\n\n"
        f"Generate a complete investor report with rankings."
    )
    return final_output.content

# ---------------------------- Streamlit UI ---------------------------- #

st.set_page_config(page_title="AI Stock Insight App", page_icon="📊", layout="wide")

st.markdown("""
    <h1 style="text-align: center; color: #2E86C1;">📊 AI Stock Insight App</h1>
    <h3 style="text-align: center; color: #7D8A95;">Discover AI-driven investment recommendations and insights.</h3>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
    <h2 style="color: #1C2833;">App Settings</h2>
    <p style="color: #566573;">Enter stock tickers below. The app will analyze each stock's performance, business profile, and suggest investment options.</p>
""", unsafe_allow_html=True)

user_input = st.sidebar.text_input("Stock Symbols (e.g. AAPL, TSLA, GOOG)", "AAPL, TSLA, GOOG")
user_api = st.sidebar.text_input("Google Gemini API Key (optional)", type="password")
parsed_symbols = [sym.strip() for sym in user_input.split(",")]

if st.sidebar.button("Run Investment Analysis"):
    if not parsed_symbols:
        st.sidebar.warning("Enter at least one valid stock symbol.")
    elif not user_api:
        st.sidebar.warning("Please input your API key.")
    else:
        final_summary = build_investment_summary(parsed_symbols)

        st.subheader("📘 Investment Summary")
        st.markdown(final_summary)

        st.info("The above report combines company info, market insights, and investment picks.")

        st.markdown("### 📈 6-Month Stock Price Chart")
        price_data = yf.download(parsed_symbols, period="6mo")['Close']

        fig = go.Figure()
        for sym in parsed_symbols:
            fig.add_trace(go.Scatter(x=price_data.index, y=price_data[sym], mode='lines', name=sym))

        fig.update_layout(title="Historical Price Movement (6-Month)",
                          xaxis_title="Date",
                          yaxis_title="Stock Price (USD)",
                          template="plotly_dark")
        st.plotly_chart(fig)
