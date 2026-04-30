Overview
This project uses multiple ML models that predict stock returns using technical indicators, new sentiment and basic financial data. Instead of relying on a single model, the system trains multiple models, each with varying complexity and accuracy, and compares their predictions to give one cohesive prediction. This model is automatic by using Github Actions to create a prediction every day and then sends the prediction to a paper trading account.
Key Features:
Uses Ridge, Random Forest, XGBoost as the models
Processes only new data by using caching
Uses free data sources and APIs
Includes sentiment analysis from news
Runs automatically every day
 With the prediction, it buys and sells to a paper trading account
Models:
Ridge Regression
Linear model with regularization
Fast and easy to interpret
Used as a baseline
Random Forest
 Uses decision trees
Captures non-linear relationships
Handles interactions between features
XGBoost
Gradient boosting model
Typically the most accurate
Requires more computation

Training and Evaluation:
Features
Technical indicators used: RSI, MACD, moving averages, volatility
Past returns
News sentiment scores
Financial metrics used: P/E, EPS, revenue growth
Target
Predicts bullish or bearish for 1, 5, and 21 days
Split
80% training, 20% testing
Data split time in order to avoid bias
Metrics
RMSE
R² score
Confidence Score
Measures how close predictions are to actual results
Scaled from 0 to 1

Data Pipeline:

Price Data
Pulled from yfinance
Only new data is downloaded
News Data
Retrieved from yfinance
Duplicate articles are removed
Sentiment is calculated using VADER
Basic Data
Uses P/E, EPS, revenue, and margins
Updated every 30 days

Feature Engineering:
Computes technical indicators
Adds sentiment and fundamental data
Uses hashing to avoid recomputing data that is unchanged
Prediction Horizons
1 day
5 days
21 days

Output:

Predicted direction (bullish or bearish)
Expected return percentage
Confidence score
Predictions from all models are combined to produce the final result.

Automation:
The model runs automatically using GitHub Actions.
Workflow:
Load cached data
Fetch new data
Update features if needed
Train and evaluate models
Creates predictions
Executes paper trades


Tech Stack
Python
scikit-learn
XGBoost
pandas and numpy
yfinance
VADER sentiment analysis
GitHub Actions

