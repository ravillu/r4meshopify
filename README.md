# Route4Me Shopify Dashboard

A dashboard for visualizing Route4Me delivery routes with associated order values.

## Features

- Display total value for all routes
- Show routes grouped by date with order values
- Calculate success rates for order values
- Export data as CSV or JSON

## Requirements

- Python 3.8+
- Flask
- Route4Me API key

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/pl-dashboard-r4me.git
   cd pl-dashboard-r4me
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```
   export ROUTE4ME_API_KEY=your_api_key
   ```
   Or create a `.env` file with:
   ```
   ROUTE4ME_API_KEY=your_api_key
   FLASK_SECRET_KEY=your_secret_key
   ```

## Usage

Run the application locally:
```
python app.py
```

Then open http://localhost:10000 in your browser.

## Deployment

### Deploy to Render.com

1. Create a new Web Service on Render.com
2. Connect your GitHub repository
3. Configure as follows:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
   - Add environment variables in the dashboard:
     - ROUTE4ME_API_KEY
     - FLASK_SECRET_KEY

### Deploy to Railway.app

1. Create new project on Railway.app
2. Connect your GitHub repository
3. Add environment variables:
   - ROUTE4ME_API_KEY
   - FLASK_SECRET_KEY

## License

MIT 