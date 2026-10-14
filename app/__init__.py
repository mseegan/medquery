import warnings

# langgraph's prebuilt ReAct agent still works; silence its migration notice.
warnings.filterwarnings("ignore", message=".*create_react_agent.*")
