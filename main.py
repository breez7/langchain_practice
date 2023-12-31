from langchain.agents import Tool, AgentExecutor, LLMSingleActionAgent, AgentOutputParser
from langchain.prompts import StringPromptTemplate
from langchain.llms import OpenAI
from langchain.utilities import SerpAPIWrapper
from langchain.chains import LLMChain
from typing import List, Union
from langchain.schema import AgentAction, AgentFinish, OutputParserException
import re
from langchain.llms import LlamaCpp
import os

import langchain
langchain.verbose = True

os.environ["SERPAPI_API_KEY"] = "7ece74cb78fae54383225ba686fe99c701063f0b108771a3df98715d9d5fc0f8"
# Define which tools the agent can use to answer user queries

def search_contact(name: str) -> str:
    return '01030752315'
def phonecall(phonenumber: str) -> str:
    return "it's called to " + phonenumber
def default(input: str) -> str:
    return 'Nothing happened'

search = SerpAPIWrapper()
tools = [
    Tool(
        name="default",
        func=default,
        description="dummy action"
    ),
    Tool(
        name="Contact",
        func=search_contact,
        description="useful for when you search a phone number by name"
    ),
    Tool(
        name="Phone",
        func=phonecall,
        description="useful for when you make a phone call using a phone number"
    ),
    Tool(
        name="Search",
        func=search.run,
        description="useful for when you need to answer questions about current events"
    )
]

# Set up the base template
# template = """Answer the following questions as best you can, but speaking as a pirate might speak. You have access to the following tools:
template = """Make a plan the following questions as best you can by step by step. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin! Use lots of "Arg"s

Question: {input}
{agent_scratchpad}"""

# Set up a prompt template
class CustomPromptTemplate(StringPromptTemplate):
    # The template to use
    template: str
    # The list of tools available
    tools: List[Tool]

    def format(self, **kwargs) -> str:
        # Get the intermediate steps (AgentAction, Observation tuples)
        # Format them in a particular way
        intermediate_steps = kwargs.pop("intermediate_steps")
        thoughts = ""
        for action, observation in intermediate_steps:
            thoughts += action.log
            thoughts += f"\nObservation: {observation}\nThought: "
        # Set the agent_scratchpad variable to that value
        kwargs["agent_scratchpad"] = thoughts
        # Create a tools variable from the list of tools provided
        kwargs["tools"] = "\n".join([f"{tool.name}: {tool.description}" for tool in self.tools])
        # Create a list of tool names for the tools provided
        kwargs["tool_names"] = ", ".join([tool.name for tool in self.tools])
        return self.template.format(**kwargs)
    
prompt = CustomPromptTemplate(
    template=template,
    tools=tools,
    # This omits the `agent_scratchpad`, `tools`, and `tool_names` variables because those are generated dynamically
    # This includes the `intermediate_steps` variable because that is needed
    input_variables=["input", "intermediate_steps"]
)
    
class CustomOutputParser(AgentOutputParser):

    def parse(self, llm_output: str) -> Union[AgentAction, AgentFinish]:
        # Check if agent should finish
        if "Final Answer:" in llm_output:
            return AgentFinish(
                # Return values is generally always a dictionary with a single `output` key
                # It is not recommended to try anything else at the moment :)
                return_values={"output": llm_output.split("Final Answer:")[-1].strip()},
                log=llm_output,
            )
        # Parse out the action and action input
        regex = r"Action\s*\d*\s*:(.*?)\nAction\s*\d*\s*Input\s*\d*\s*:[\s]*(.*)"
        match = re.search(regex, llm_output, re.DOTALL)
        if not match:
            return AgentAction(tool='default', tool_input=llm_output, log =llm_output)
            # raise OutputParserException(f"Could not parse LLM output: `{llm_output}`")
        action = match.group(1).strip()
        action_input = match.group(2)
        # Return the action and action input
        return AgentAction(tool=action, tool_input=action_input.strip(" ").strip('"'), log=llm_output)
    
output_parser = CustomOutputParser()
# llm = LlamaCpp(model_path='/mnt/c/llama/models/llama-2-7b-chat.Q4_0.gguf',
llm = LlamaCpp(model_path='/mnt/c/llama/models/sheep-duck-llama-2-13b.Q4_K_M.gguf',
               n_gpu_layers=100,
               n_batch=512,
               n_ctx=4096,
               )

# LLM chain consisting of the LLM and a prompt
llm_chain = LLMChain(llm=llm, prompt=prompt)
tool_names = [tool.name for tool in tools]
agent = LLMSingleActionAgent(
    llm_chain=llm_chain,
    output_parser=output_parser,
    stop=["\nObservation:"],
    allowed_tools=tool_names
)

agent_executor = AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)

# agent_executor.run("How many people live in canada as of 2023?")
while(True):
    input_text = input()
    agent_executor.run(input_text)
