import streamlit as st
import matplotlib.pyplot as plt
from fpdf import FPDF
import base64
import pandas as pd

# Set page config
st.set_page_config(page_title="Submersible Pump Selector", layout="wide")

# Pipe sizing recommendations
PIPE_SIZING = {
    "32": {"Max Flow (LPH)": 2000, "Velocity (m/s)": 0.7},
    "40": {"Max Flow (LPH)": 4000, "Velocity (m/s)": 0.9},
    "50": {"Max Flow (LPH)": 7000, "Velocity (m/s)": 1.0},
    "63": {"Max Flow (LPH)": 12000, "Velocity (m/s)": 1.1},
    "75": {"Max Flow (LPH)": 18000, "Velocity (m/s)": 1.2},
    "90": {"Max Flow (LPH)": 25000, "Velocity (m/s)": 1.3}
}

# Hazen-Williams C values
C_VALUES = {"PVC": 140, "GI": 120}

def create_pdf_report(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Title
    pdf.cell(200, 10, txt="Submersible Pump Selection Report", ln=1, align='C')
    pdf.ln(10)

    # Input Parameters
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Input Parameters:", ln=1)
    pdf.set_font("Arial", size=10)

    for param, value in data['inputs'].items():
        safe_value = str(value).encode('ascii', 'ignore').decode('ascii')
        safe_param = str(param).encode('ascii', 'ignore').decode('ascii')
        pdf.cell(200, 6, txt=f"{safe_param}: {safe_value}", ln=1)

    # Results
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Calculation Results:", ln=1)
    pdf.set_font("Arial", size=10)

    for result, value in data['results'].items():
        safe_value = str(value).replace(',', '').encode('ascii', 'ignore').decode('ascii')
        safe_result = str(result).encode('ascii', 'ignore').decode('ascii')
        pdf.cell(200, 6, txt=f"{safe_result}: {safe_value}", ln=1)

    # Recommendations
    if 'recommendations' in data:
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="Recommendations:", ln=1)
        pdf.set_font("Arial", size=10)

        for rec in data['recommendations']:
            safe_rec = str(rec).encode('ascii', 'ignore').decode('ascii')
            pdf.cell(200, 6, txt=f"- {safe_rec}", ln=1)

    # Return as bytes
    return pdf.output(dest='S').encode('latin-1')

# Load pump data function with more robust column name handling
def load_pump_data():
    try:
        pump_data = pd.read_excel("Pumps.xlsx")
        
        # Standardize column names (case insensitive, strip whitespace)
        pump_data.columns = [col.strip().lower() for col in pump_data.columns]
        
        # Map expected column names to possible variations
        column_mapping = {
            'pump': ['pump', 'model', 'pump model'],
            'phase': ['phase', 'power phase', 'type'],
            'hp': ['hp', 'horsepower', 'power'],
            'qmin': ['qmin', 'min flow', 'minimum flow (lph)'],
            'qmax': ['qmax', 'max flow', 'maximum flow (lph)'],
            'hmin': ['hmin', 'min head', 'minimum head (m)'],
            'hmax': ['hmax', 'max head', 'maximum head (m)']
        }
        
        # Find matching columns
        final_columns = {}
        for standard_name, possible_names in column_mapping.items():
            for possible_name in possible_names:
                if possible_name in pump_data.columns:
                    final_columns[standard_name] = possible_name
                    break
        
        # Check if we found all required columns
        required_columns = ['pump', 'phase', 'hp', 'qmin', 'qmax', 'hmin', 'hmax']
        missing_columns = [col for col in required_columns if col not in final_columns]
        
        if missing_columns:
            st.error(f"Missing required columns in Excel file: {', '.join(missing_columns)}")
            st.error("Please ensure your Excel file has columns for: Pump, Phase, HP, Qmin, Qmax, Hmin, Hmax")
            return None
        
        # Rename columns to standard names
        pump_data = pump_data.rename(columns={v: k for k, v in final_columns.items()})
        
        # Convert numeric columns to appropriate types
        numeric_cols = ['hp', 'qmin', 'qmax', 'hmin', 'hmax']
        for col in numeric_cols:
            pump_data[col] = pd.to_numeric(pump_data[col], errors='coerce')
        
        # Sort by HP and then by Hmax (low to high)
        pump_data = pump_data.sort_values(['hp', 'hmax'])
        
        return pump_data
    
    except Exception as e:
        st.error(f"Error loading pump database: {str(e)}")
        return None

# Revised pump selection function
def select_pump(pump_data, required_hp, required_flow_lph, required_tdh):
    # First try to find exact HP match
    exact_hp_pumps = pump_data[pump_data['hp'] == required_hp]
    
    # If exact HP exists, check flow and head range
    if not exact_hp_pumps.empty:
        for _, pump in exact_hp_pumps.iterrows():
            if (pump['qmin'] <= required_flow_lph <= pump['qmax']) and \
               (pump['hmin'] <= required_tdh <= pump['hmax']):
                return pump, "exact_match"
        
        # If no exact HP with sufficient flow/head, try next higher HP
        higher_hp_pumps = pump_data[pump_data['hp'] > required_hp]
        if not higher_hp_pumps.empty:
            for _, pump in higher_hp_pumps.iterrows():
                if (pump['qmin'] <= required_flow_lph <= pump['qmax']) and \
                   (pump['hmin'] <= required_tdh <= pump['hmax']):
                    return pump, "higher_hp_match"
    
    # If no matches yet, find first pump with HP >= required_hp that meets head requirements
    suitable_pumps = pump_data[pump_data['hp'] >= required_hp]
    if not suitable_pumps.empty:
        for _, pump in suitable_pumps.iterrows():
            if pump['hmin'] <= required_tdh <= pump['hmax']:
                return pump, "tdh_match"
    
    # Final fallback - highest capacity pump
    return pump_data.iloc[-1], "last_resort"

# Main app
st.title("Submersible Pump Selector")
st.markdown("""
This tool calculates the required **TDH**, **Pump HP**,**Discharge Range** and  **Head Range** for a submersible pump in water supply systems.
The calculations consider pipe friction losses, velocity head, and include safety margins.
""")

# Inputs section
col1, col2 = st.columns(2)

with col1:
    st.subheader("System Requirements")
    yield_lph = st.number_input("Borewell Yield (LPH)", min_value=100.0, step=50.0, value=2000.0)
    num_taps = st.number_input("Total Tap Connections", min_value=1, step=1, value=20)
    demand_per_tap = st.number_input("Daily Water Demand per Tap (Liters)", min_value=10, step=10, value=50)
    pumping_hours = st.number_input("Hours Available for Pumping", min_value=0.5, max_value=24.0, step=0.5, value=6.0)
    
    st.subheader("Physical Layout")
    installation_depth = st.number_input("Pump Installation Depth (m)", min_value=1.0, step=0.5, value=30.0)
    tank_height = st.number_input("Tank Height from Ground (m)", min_value=0.0, step=0.5, value=10.0)
    pumping_line_length = st.number_input("Pumping Line Length (m)", min_value=1.0, step=1.0, value=50.0)

with col2:
    st.subheader("Piping System")
    pipe_diameter_mm = st.selectbox("Pumping Line Diameter (mm)", [32, 40, 50, 63, 75, 90], index=2)
    pipe_type = st.selectbox("Piping Material", ["PVC", "GI"], index=0)
    
    st.subheader("Pump Parameters")
    safety_margin = st.number_input("Safety Margin (%)", value=15.0, min_value=0.0, max_value=100.0)
    efficiency = st.number_input("Pump Efficiency (%)", value=65.0, min_value=30.0, max_value=90.0)
    head_per_stage = st.number_input("Head per Pump Stage (m)", value=5.0, min_value=1.0, max_value=20.0)

# Calculations
if st.button("Calculate Pump Requirements"):
    # Basic calculations
    demand_liters = num_taps * demand_per_tap
    flow_lph = demand_liters / pumping_hours
    flow_m3ps = flow_lph / 3600000
    
    # Check yield sufficiency
    if flow_lph > yield_lph:
        st.error("⚠️ Required flow exceeds borewell yield! Reduce demand or increase pumping hours.")
        st.stop()
    
    # Pipe calculations
    pipe_diameter_m = pipe_diameter_mm / 1000.0
    C = C_VALUES.get(pipe_type, 140)
    
    # Friction loss (Hazen-Williams)
    friction_loss = (10.67 * pumping_line_length * (flow_m3ps**1.852)) / (C**1.852 * pipe_diameter_m**4.87)
    minor_losses = 0.10 * friction_loss  # 10% for fittings
    total_pipe_loss = friction_loss + minor_losses
    
    # Velocity head
    pipe_area = 3.1416 * (pipe_diameter_m**2) / 4
    velocity = flow_m3ps / pipe_area
    velocity_head = (velocity**2) / (2 * 9.81)
    
    # TDH calculation
    static_head = installation_depth + tank_height
    tdh_without_safety = static_head + total_pipe_loss + velocity_head
    safety_margin_value = (safety_margin / 100) * tdh_without_safety
    tdh = tdh_without_safety + safety_margin_value
    
    # Pump power
    hp = (flow_m3ps * tdh * 1000 * 9.81) / (efficiency/100 * 745.7)
    hp_rounded = max(0.5, round(hp + 0.4))  # Round up to nearest 0.5 HP
    kw = hp * 0.7457
    
    # Number of stages (now just informational, not used for selection)
    num_stages = int(tdh / head_per_stage + 0.5)
    
    # Results display
    st.subheader("Results")
    
    col_res1, col_res2 = st.columns(2)
    
    with col_res1:
        st.markdown(f"""
        **Hydraulic Requirements:**
        - Total Daily Demand: {demand_liters:,.0f} liters
        - Required Flow Rate: {flow_lph:,.0f} LPH ({flow_m3ps*1000:.2f} L/s)
        - Total Dynamic Head (TDH): {tdh:.1f} m
        """)
        
        # TDH Breakdown
        with st.expander("Head Loss Breakdown"):
            st.markdown(f"""
            - Static Head: {static_head:.1f} m
            - Pipe Friction Loss: {total_pipe_loss:.1f} m
            - Velocity Head: {velocity_head:.2f} m
            - Safety Margin: {safety_margin_value:.1f} m
            """)
    
    with col_res2:
        st.markdown(f"""
        **Pump Specifications:**
        - Required Power: {hp:.1f} HP → **Use {hp_rounded} HP** ({kw:.1f} kW)
        - Estimated Stages: {num_stages} (based on {head_per_stage}m per stage)
        - Recommended RPM: 2850 (for standard 4" pumps)
        """)
    
    # Pipe sizing check
    st.subheader("Pipe Sizing Evaluation")
    selected_pipe = str(pipe_diameter_mm)
    pipe_max_flow = PIPE_SIZING[selected_pipe]["Max Flow (LPH)"]
    pipe_velocity = PIPE_SIZING[selected_pipe]["Velocity (m/s)"]
    
    velocity_status = "✅ Good" if velocity <= pipe_velocity else "⚠️ High - Consider larger pipe"
    
    st.markdown(f"""
    - Selected Pipe: {pipe_diameter_mm}mm {pipe_type}
    - Actual Flow Velocity: {velocity:.2f} m/s ({velocity_status})
    - Recommended Max Flow for this pipe: {pipe_max_flow:,} LPH
    """)
    
    if velocity > pipe_velocity:
        st.warning("High velocity detected! Consider increasing pipe size to reduce friction losses.")
    
    # Load pump data and select pump
    pump_data = load_pump_data()
    
    if pump_data is not None:
        selected_pump, match_type = select_pump(pump_data, hp_rounded, flow_lph, tdh)
        
        # Display pump selection with appropriate message
        st.subheader("Recommended Pump")
        col_pump1, col_pump2 = st.columns(2)
        
        with col_pump1:
            st.markdown(f"""
            **Model:** {selected_pump['pump']}  
            **Phase:** {selected_pump['phase']}  
            **Power:** {selected_pump['hp']} HP  
            **Flow Range:** {selected_pump['qmin']}-{selected_pump['qmax']} LPH  
            """)
            
        with col_pump2:
            st.markdown(f"""
            **Head Range:** {selected_pump['hmin']}-{selected_pump['hmax']} m  
            **Your TDH:** {tdh:.1f} m  
            **Your Flow:** {flow_lph:,.0f} LPH  
            **Compatibility:** {'✅ Within range' if selected_pump['hmin'] <= tdh <= selected_pump['hmax'] and selected_pump['qmin'] <= flow_lph <= selected_pump['qmax'] else '⚠️ Outside optimal range'}  
            """)
        
        # Add match type explanation
        if match_type == "exact_match":
            st.success("Found pump matching exact HP, flow, and head requirements")
        elif match_type == "higher_hp_match":
            st.warning(f"Using higher HP pump ({selected_pump['hp']} HP) that meets flow and head requirements")
        elif match_type == "tdh_match":
            st.warning("Selected pump based on TDH requirements with different flow characteristics")
        else:
            st.error("No suitable pump found - showing highest capacity option")
        
        # Prepare report data
        report_data = {
            'inputs': {
                'Borewell Yield (LPH)': f"{yield_lph:,.0f}",
                'Total Tap Connections': num_taps,
                'Daily Water Demand per Tap (Liters)': demand_per_tap,
                'Hours Available for Pumping': pumping_hours,
                'Pump Installation Depth (m)': installation_depth,
                'Tank Height from Ground (m)': tank_height,
                'Pumping Line Length (m)': pumping_line_length,
                'Pipe Diameter (mm)': pipe_diameter_mm,
                'Pipe Material': pipe_type,
                'Safety Margin (%)': safety_margin,
                'Pump Efficiency (%)': efficiency,
                'Head per Pump Stage (m)': head_per_stage,
            },
            'results': {
                'Total Daily Demand (liters)': f"{demand_liters:,.0f}",
                'Required Flow Rate (LPH)': f"{flow_lph:,.0f}",
                'Total Dynamic Head (TDH)': f"{tdh:.1f} m",
                'Required Power': f"{hp:.1f} HP → Use {hp_rounded} HP",
                'Estimated Stages': num_stages,
                'Flow Velocity (m/s)': f"{velocity:.2f}",
                'Pipe Sizing Status': velocity_status
            },
            'recommendations': [
                f"Recommended pump: {selected_pump['pump']} ({selected_pump['hp']} HP)",
                f"Flow range of pump: {selected_pump['qmin']} - {selected_pump['qmax']} LPH",
                f"Head range of pump: {selected_pump['hmin']} - {selected_pump['hmax']} m",
                f"TDH falls within range: {'Yes' if selected_pump['hmin'] <= tdh <= selected_pump['hmax'] else 'No'}",
                f"Flow rate falls within range: {'Yes' if selected_pump['qmin'] <= flow_lph <= selected_pump['qmax'] else 'No'}"
            ]
        }

        # Generate PDF
        pdf_bytes = create_pdf_report(report_data)
        b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        href = f'<a href="data:application/octet-stream;base64,{b64_pdf}" download="Pump_Selection_Report.pdf">📄 Download PDF Report</a>'
        st.markdown(href, unsafe_allow_html=True)

# Add some spacings
st.markdown("---")
st.markdown("""
**Instructions:**
1. Fill in all system parameters
2. Click 'Calculate Pump Requirements'
""")
