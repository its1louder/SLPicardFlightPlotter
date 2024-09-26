import streamlit as st
import numpy as np
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.style as style
import matplotlib.patches as patches
import matplotlib.table as tbl
import datetime as dt
import base64
import os

style.use('bmh')
SEPCHAR = "PICARD"
URL = "https://asp-interface.arc.nasa.gov/API/parameter_data/N806NA/PICARD?Start=0"
COLNAMES = ['Status', 'Pressure', 'ambient_temp', 'heater_blower_out', 'shutter','case',
            'power_board', 'vnir_det_focuser', 'dctec_hot', 'dctec_cold',
            'pidtec_hot', 'pidtec_cold', 'pipe_temp_diff']

def scrape_data(url):
    r = requests.get(url)
    html = str(r.content)
    msglst = [l[:-3] for l in html.split(SEPCHAR) if len(l)>1]
    return msglst[1:]

def clean_data(msglst, maskcols=COLNAMES[2:-1], minval=-10.0, maxval=100.0):
    data = [line.split(",") for line in msglst]
    df = pd.DataFrame(data)
    df.set_index(1, inplace=True)
    df = df.iloc[:, 1:]
    df.index = pd.to_datetime(df.index)
    df.columns = COLNAMES[:-1]
    df.index.name = 'Time'
    df = df.astype(float)
    for column_name in maskcols:
        df[column_name] = df[column_name].where(df[column_name].between(minval, maxval), np.nan)
    df[COLNAMES[-1]] = df['pidtec_hot'] - df['dctec_cold']
    return df

def plot_temp_data(df, datestmp, cols=COLNAMES[2:]):
    fig, ax = plt.subplots()
    sorted_cols = df[cols].iloc[-1].sort_values(ascending=False).index
    df[sorted_cols].plot(ax=ax, legend=False, grid=True, title=f"{datestmp} PICARD Temperatures")
    
    # Prepend the last value to the label
    labels = ['{:.2f} {:<5}'.format(df[col].iloc[-1], col) for col in sorted_cols]
    
    legend = ax.legend(labels, bbox_to_anchor=(1.05, 1), loc='upper left')  
    return fig

def plot_pressure_data(df, datestmp, cols=COLNAMES[1],):
    fig, ax = plt.subplots()
    df[cols].plot(ax=ax, legend=True, grid=True, title=f"{datestmp} PICARD Pressure")
    return fig
    
def save_data(df, datestmp):
    hk_file = f'/srv/podlog.d/{datestmp}_PICARD_HK.h5'
    with pd.HDFStore(hk_file) as dstore:
        dstore['PICARD_HK'] = df
    return hk_file

def get_binary_file_downloader_html(bin_file, file_label='File'):
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{bin_str}" download="{os.path.basename(bin_file)}">{file_label}</a>'
    return href


def display_status(df, now=None, freshness=15):
    # Default to current time if not provided
    if now is None:
        now = dt.datetime.now()

    # Set up layout with two columns
    col1, col2 = st.columns(2)

    # Check recording status
    status = df["Status"].values[-1]
    with col1:
        if status == 2:
            st.success('Recording')
        else:
            st.error('Not Recording')

    # Check status freshness
    last_timestamp = df.index[-1]
    time_diff = now - last_timestamp
    freshness_diff = dt.timedelta(seconds=freshness)
    with col2:
        if time_diff <= freshness_diff:
            st.success('Status Fresh')
        else:
            st.error('Status Stale')

def slmain():
    
    st.title("PICARD status packet plotter")

    url = st.text_input("URL", URL)
    freshness = st.number_input('Freshness', min_value=2, max_value=200000,  value="min", )
    if st.button('Scrape and Plot Data'):
        msglst = scrape_data(url)
        df = clean_data(msglst)
        datestmp = df.index[0].strftime("%Y-%m-%d")

        display_status(df, freshness=freshness)
        
        st.pyplot(plot_temp_data(df,datestmp))
        
        # this line to save the data will only work on local deployment, not on streamlit cloud
        picard_file = save_data(df, datestmp)
        st.markdown(get_binary_file_downloader_html(picard_file, 'Download PICARD HK Data'), unsafe_allow_html=True)
        st.write (df)
        st.pyplot(plot_pressure_data(df,datestmp))

if __name__ == "__main__":
    slmain()