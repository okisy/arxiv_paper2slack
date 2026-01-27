# settings
keywords_ai = '"Deep Learning" OR "Machine Learning" OR "Neural Network" OR "Graph Neural Network" OR "GNN" OR "Transformer" OR "Representation Learning"'
keywords_domain = '"Network Traffic" OR "Traffic Prediction" OR "Mobile Network" OR "5G" OR "6G" OR "Geospatial" OR "Spatiotemporal" OR "Urban Computing" OR "Human Mobility" OR "Spatial Trajectory" OR "Smart City" OR "Crowd Flow" OR "Intelligent Transportation" OR "SIGSPATIAL" OR "KDD" OR "Ubicomp" OR "PerCom" OR "RecSys" OR "WWW conference" OR "TheWebConf" OR "ICDM"'
ARXIV_QUERY = f'({keywords_ai}) AND ({keywords_domain})'
MAX_RESULTS = 100
NUM_PAPERS = 3
SLACK_CHANNEL = "#general"
SLACK_PROMPT_CHANNEL = "#all-arxiv-paper-notification"
