const chatCompletionLLMSpanAttributes = {
  //   input: {
  //     mime_type: "application/json",
  //     value:
  //       '{"messages": [{"role": "system", "content": "You are an expert Q&A system that is trusted around the world.\\nAlways answer the query using the provided context information, and not prior knowledge.\\nSome rules to follow:\\n1. Never directly reference the given context in your answer.\\n2. Avoid statements like \'Based on the context, ...\' or \'The context information ...\' or anything along those lines.", "additional_kwargs": {}}, {"role": "user", "content": "Context information is below.\\n---------------------\\nsource: https://docs.arize.com/phoenix/tracing/concepts-tracing/what-are-traces\\ntitle: Traces\\n\\nNot more than 4-1/4 inches high, or more than 6 inches long, or greater than \\\\n0.016 inch thick.\\\\nd. Not more than 3.5 ounces (Charge flat-size prices for First-Class Mail \\\\ncard-type pieces over 3.5 ounces.)\\\\n\\\\n  Instruction: Based on the above documents, provide a detailed answer for the user question below.\\\\n  Answer \\\\\\"don\'t know\\\\\\" if not present in the document.\\\\n  \\",\\n\\n\\n       \\n\\"llm.input_messages.1.message.role\\"\\n:\\n \\n\\"user\\"\\n,\\n\\n\\n       \\n\\"llm.input_messages.1.message.content\\"\\n:\\n \\n\\"Hello\\"\\n,\\n\\n\\n       \\n\\"llm.model_name\\"\\n:\\n \\n\\"gpt-4-turbo-preview\\"\\n,\\n\\n\\n       \\n\\"llm.invocation_parameters\\"\\n:\\n \\n\\"{\\\\\\"temperature\\\\\\": 0.1, \\\\\\"model\\\\\\": \\\\\\"gpt-4-turbo-preview\\\\\\"}\\"\\n,\\n\\n\\n       \\n\\"output.value\\"\\n:\\n \\n\\"How are you?\\"\\n }\\n,\\n\\n\\n   \\n\\"events\\"\\n:\\n []\\n,\\n\\n\\n   \\n\\"links\\"\\n:\\n []\\n,\\n\\n\\n   \\n\\"resource\\"\\n:\\n {\\n\\n\\n       \\n\\"attributes\\"\\n:\\n {}\\n,\\n\\n\\n       \\n\\"schema_url\\"\\n:\\n \\n\\"\\"\\n\\n\\n   }\\n\\n\\n}\\nSpans can be nested, as is implied by the presence of a parent span ID: child spans represent sub-operations. This allows spans to more accurately capture the work done in an application.\\nTraces\\nA trace records the paths taken by requests (made by an application or end-user) as they propagate through multiple steps.\\nWithout tracing, it is challenging to pinpoint the cause of performance problems in a system.\\nIt improves the visibility of our application or system\\u2019s health and lets us debug behavior that is difficult to reproduce locally. Tracing is essential for LLM applications, which commonly have nondeterministic problems or are too complicated to reproduce locally.\\nTracing makes debugging and understanding LLM applications less daunting by breaking down what happens within a request as it flows through a system.\\nA trace is made of one or more spans. The first span represents the root span. Each root span represents a request from start to finish. The spans underneath the parent provide a more in-depth context of what occurs during a request (or what steps make up a request).\\nProjects\\nA \\nproject\\n is a collection of traces. You can think of a project as a container for all the traces that are related to a single application or service. You can have multiple projects, and each project can have multiple traces. Projects can be useful for various use-cases such as separating out environments, logging traces for evaluation runs, etc. To learn more about how to setup projects,  see the \\nhow-to guide.\\nSpan Kind\\nWhen a span is created,  it is created as one of the following: Chain, Retriever, Reranker, LLM, Embedding, Agent, or Tool. \\nCHAIN\\nA Chain is a starting point or a link between different LLM application steps. For example, a Chain span could be used to represent the beginning of a request to an LLM application or the glue code that passes context from a retriever to and LLM call.\\nRETRIEVER\\nA Retriever is a span that represents a data retrieval step. For example, a Retriever span could be used to represent a call to a vector store or a database.\\nRERANKER\\nA Reranker is a span that represents the reranking of a set of input documents. For example, a cross-encoder may be used to compute the input documents\' relevance scores with respect to a user query, and the top K documents with the highest scores are then returned by the Reranker.\\nLLM\\nAn LLM is a span that represents a call to an LLM. For example, an LLM span could be used to represent a call to OpenAI or Llama.\\nEMBEDDING\\nAn Embedding is a span that represents a call to an LLM for an embedding. For example, an Embedding span could be used to represent a call OpenAI to get an ada-2 embedding for retrieval.\\nTOOL\\nA Tool is a span that represents a call to an external tool such as a calculator or a weather API.\\nAGENT\\nA span that encompasses calls to LLMs and Tools. An agent describes a reasoning block that acts on tools using the guidance of an LLM.\\n\\nSpan Attributes\\nAttributes are key-value pairs that contain metadata that you can use to annotate a span to carry information about the operation it is tracking.\\nFor example, if a span invokes an LLM, you can capture the model name, the invocation parameters, the token count, and so on.\\nAttributes have the following rules:\\nKeys must be non-null string values\\nValues must be a non-null string, boolean, floating point value, integer, or an array of these values Additionally, there are Semantic Attributes, which are known naming conventions for metadata that is typically present in common operations. It\'s helpful to use semantic attribute naming wherever possible so that common kinds of metadata are standardized across systems. See \\nsemantic conventions\\n for more information.\\n\\nsource: https://docs.arize.com/phoenix/tracing/llm-traces\\ntitle: Overview: Tracing\\n\\nOverview: Tracing\\nTracing the execution of LLM applications using Telemetry\\nLLM tracing records the paths taken by requests as they propagate through multiple steps or components of an LLM application. For example, when a user interacts with an LLM application, tracing can capture the sequence of operations, such as document retrieval, embedding generation, language model invocation, and response generation to provide a detailed timeline of the request\'s execution.\\nTracing is a helpful tool for understanding how your LLM application works. Phoenix offers comprehensive tracing capabilities that are not tied to any specific LLM vendor or framework. Phoenix accepts traces over the OpenTelemetry protocol (OTLP) and supports first-class instrumentation for a variety of frameworks ( \\nLlamaIndex\\n, \\nLangChain\\n,\\n DSPy\\n),  SDKs (\\nOpenAI\\n, \\nBedrock\\n, \\nMistral\\n, \\nVertex\\n), and Languages. (Python, Javascript, etc.)\\nUsing Phoenix\'s tracing capabilities can provide important insights into the inner workings of your LLM application. By analyzing the collected trace data, you can identify and address various performance and operational issues and improve the overall reliability and efficiency of your system.\\nApplication Latency\\n: Identify and address slow invocations of LLMs, Retrievers, and other components within your application, enabling you to optimize performance and responsiveness.\\nToken Usage\\n: Gain a detailed breakdown of token usage for your LLM calls, allowing you to identify and optimize the most expensive LLM invocations.\\nRuntime Exceptions\\n: Capture and inspect critical runtime exceptions, such as rate-limiting events, that can help you proactively address and mitigate potential issues.\\nRetrieved Documents\\n: Inspect the documents retrieved during a Retriever call, including the score and order in which they were returned to provide insight into the retrieval process.\\nEmbeddings\\n: Examine the embedding text used for retrieval and the underlying embedding model to allow you to validate and refine your embedding strategies.\\nLLM Parameters\\n: Inspect the parameters used when calling an LLM, such as temperature and system prompts, to ensure optimal configuration and debugging.\\nPrompt Templates\\n: Understand the prompt templates used during the prompting step and the variables that were applied, allowing you to fine-tune and improve your prompting strategies.\\nTool Descriptions\\n: View the descriptions and function signatures of the tools your LLM has been given access to in order to better understand and control your LLM\\u2019s capabilities.\\nLLM Function Calls\\n: For LLMs with function call capabilities (e.g., OpenAI), you can inspect the function selection and function messages in the input to the LLM, further improving your ability to debug and optimize your application.\\nBy using tracing in Phoenix, you can gain increased visibility into your LLM application, empowering you to identify and address performance bottlenecks, optimize resource utilization, and ensure the overall reliability and effectiveness of your system.\\nView the inner workings for your LLM Application\\nTo get started, check out the \\nQuickstart guide\\nAfter that, read through the \\nConcepts Section\\n to get and understanding of the different components.\\nIf you want to learn how to accomplish a particular task, check out the \\nHow-To Guides.\\n\\n\\nPrevious\\nFAQs: Deployment\\nNext\\nQuickstart: Tracing\\nLast updated \\n6 hours ago\\n---------------------\\nGiven the context information and not prior knowledge, answer the query.\\nQuery: Can I use gRPC for trace collection?\\nAnswer: ", "additional_kwargs": {}}]}',
  //   },
  llm: {
    output_messages: [
      {
        message: {
          content: "This is an AI Answer",
          role: "assistant",
        },
      },
    ],
    model_name: "gpt-3.5-turbo",
    token_count: { completion: 9.0, prompt: 1881.0, total: 1890.0 },
    input_messages: [
      {
        message: {
          content: "You are a chatbot",
          role: "system",
        },
      },
      {
        message: {
          content: "Anser me the following question. Are you sentient?",
          role: "user",
        },
      },
    ],
    invocation_parameters:
      '{"context_window": 16384, "num_output": -1, "is_chat_model": true, "is_function_calling_model": true, "model_name": "gpt-3.5-turbo"}',
  },
  openinference: { span: { kind: "LLM" } },
  //   output: { value: "assistant: You can use gRPC for trace collection." },
};

describe("spanUtils", () => {
  it("should convert a chat completion llm span to an invocation object type", () => {
    const result = llmSpanToInvocation(chatCompletionLLMSpanAttributes);
    expect(result).toEqual({});
  });
});
