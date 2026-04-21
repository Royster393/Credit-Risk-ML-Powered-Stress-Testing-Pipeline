import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# --- CONFIGURATION ---
SERVER_NAME = r'LOCALHOST\SQLEXPRESS' 
DATABASE_NAME = 'FinancePortfolioDB'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_FILE = os.path.join(BASE_DIR, 'csv', 'credit_risk_dataset.csv')

def run_ml_risk_pipeline():
    print(f"--- Deploying ML-Powered Pipeline for {SERVER_NAME} ---")
    
    if not os.path.exists(LOCAL_FILE):
        print(f"ERROR: Cannot find file at: {LOCAL_FILE}")
        return

    # Coordinates for the Dimension Table (Restored)
    branch_coords = {
        'Windsor':   {'Lat': 42.3149, 'Lon': -83.0364},
        'Toronto':   {'Lat': 43.6532, 'Lon': -79.3832},
        'Ottawa':    {'Lat': 45.4215, 'Lon': -75.6972},
        'London':    {'Lat': 42.9849, 'Lon': -81.2496},
        'Hamilton':  {'Lat': 43.2557, 'Lon': -79.8711},
        'Kitchener': {'Lat': 43.4516, 'Lon': -80.4925}
    }

    try:
        # 1. EXTRACT & CLEAN
        df = pd.read_csv(LOCAL_FILE)
        df = df[df['person_age'] < 95]
        df['person_emp_length'] = df['person_emp_length'].fillna(df['person_emp_length'].median())
        df['loan_int_rate'] = df['loan_int_rate'].fillna(df['loan_int_rate'].median())

        # 2. MACHINE LEARNING PREPARATION
        le = LabelEncoder()
        categorical_cols = ['person_home_ownership', 'loan_intent', 'loan_grade', 'cb_person_default_on_file']
        for col in categorical_cols:
            df[col + '_n'] = le.fit_transform(df[col])

        # Geographic Assignment
        cities = list(branch_coords.keys())
        df['City'] = np.random.choice(cities, size=len(df))

        # Define Features (X) and Target (y)
        features = ['person_age', 'person_income', 'person_emp_length', 'loan_amnt', 
                    'loan_int_rate', 'person_home_ownership_n', 'loan_intent_n', 'loan_grade_n']
        X = df[features]
        y = df['loan_status'] 

        # 3. TRAIN THE MODEL
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)

        # 4. GENERATE PREDICTIONS
        df['Default_Probability'] = model.predict_proba(X[features])[:, 1]
        df['Risk_Level'] = np.where(df['Default_Probability'] > 0.5, 'High Risk (ML Predicted)', 'Standard')

        # 5. LOAD TO SQL
        engine = create_engine(f'mssql+pyodbc://@{SERVER_NAME}/{DATABASE_NAME}?driver=ODBC+Driver+17+for+SQL+Server')
        
        if 'id' not in df.columns:
            df['id'] = df.index

        # --- Table 1: Fact_Credit_Risk ---
        fact_cols = [
            'id', 'person_age', 'person_income', 'loan_amnt', 'loan_status', 'Risk_Level', 
            'Default_Probability', 'loan_grade', 'loan_intent', 'City',
            'person_home_ownership', 'cb_person_default_on_file', 'loan_int_rate'
        ]
        df[fact_cols].to_sql('Fact_Credit_Risk', engine, if_exists='replace', index=False)

        # --- Table 2: Dim_Locations (Restored) ---
        dim_location_data = {
            'City': list(branch_coords.keys()),
            'Province': ['Ontario'] * len(branch_coords),
            'Latitude': [v['Lat'] for v in branch_coords.values()],
            'Longitude': [v['Lon'] for v in branch_coords.values()]
        }
        pd.DataFrame(dim_location_data).to_sql('Dim_Locations', engine, if_exists='replace', index=False)
        
        print(f"SUCCESS: ML Model deployed. Fact and Dim tables created.")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    run_ml_risk_pipeline()