# BestPrice
It is an tool which tracks the price of product and helps user to decide weather he is getting a good bargain or not.
1. Data Collection
Option 1: Scraping (Realistic but tricky)
Tools: BeautifulSoup, Selenium, or Scrapy

Source: Flipkart

Attributes to collect:

Product name

MRP

Price

Date of collection

Category (electronics, clothing, etc.)

Scraping big e-commerce sites may block your IP. So better to simulate or collect periodically in small amounts.

Option 2: Simulated Dataset (Good for MVP)
You can create a CSV file with:

product_name, category,MRP ,current_price, discount_percent, rating, date, festival_day (Y/N)

You can generate this using Python or Excel randomly over 30–90 days of "simulated" sale events.

2. Data Preprocessing
Calculate discount % = (original_price(MRP) - current_price) / original_price(MRP)

One-hot encode category and brand

Normalize or scale prices and ratings

Add a new label:

is_bargain = 1 If current_price is 5% near historical low 

is_bargain = 0 otherwise (you can adjust logic)

-> Record the Highest discount given  in 90 day and show it's price [historical low]

3. Model Building
  A. Binary Classification:
    Is this a bargain deal or not?

Algorithms: Logistic Regression, Random Forest, XGBoost

Metrics: Accuracy, F1 Score

4. Trend Analysis (Optional Enhancement)
  Use time-series data to detect if a product price consistently drops before big sales

Use Rolling Average, EWMA (Exponential Moving Average) for smoothing

5. Interface Ideas
 You can use:

Streamlit to create a simple frontend where users can input product details

Show:

Discount trend

Fair price prediction

Whether it's a bargain

 6. Visualization
->Plot price trends of specific products over time, Important feature

Show discount distributions across categories

Compare average festival discounts vs non-festival
