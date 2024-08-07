import modal

vllm_image = modal.Image.debian_slim(python_version="3.10").pip_install(
    "vllm==0.5.3post1"
)

MODELS_DIR = "/llamas"
MODEL_NAME = "meta-llama/Meta-Llama-3.1-8B-Instruct"
MODEL_REVISION = "8c22764a7e3675c50d4c7c9a4edb474456022b16"

try:
    volume = modal.Volume.lookup("llamas", create_if_missing=False)
except modal.exception.NotFoundError:
    raise Exception("Volume not found. Please run download_llama.py first.")

app = modal.App("vllm-inference")

N_GPU = 1
TOKEN = "super-secret-token"

MINUTES = 60
HOURS = 60 * MINUTES


def get_model_config(engine):
    import asyncio

    try:  # adapted from vLLM source -- https://github.com/vllm-project/vllm/blob/507ef787d85dec24490069ffceacbd6b161f4f72/vllm/entrypoints/openai/api_server.py#L235C1-L247C1
        event_loop = asyncio.get_running_loop()
    except RuntimeError:
        event_loop = None

    if event_loop is not None and event_loop.is_running():
        # If the current is instanced by Ray Serve,
        # there is already a running event loop
        model_config = event_loop.run_until_complete(engine.get_model_config())
    else:
        # When using single vLLM without engine_use_ray
        model_config = asyncio.run(engine.get_model_config())

    return model_config


@app.function(
    image=vllm_image,
    gpu=modal.gpu.A100(count=N_GPU, size="40GB"),
    container_idle_timeout=5 * MINUTES,
    timeout=24 * HOURS,
    allow_concurrent_inputs=100,
    volumes={MODELS_DIR: volume},
)
@modal.asgi_app()
def serve():
    import fastapi
    import vllm.entrypoints.openai.api_server as api_server
    from vllm.engine.arg_utils import AsyncEngineArgs
    from vllm.engine.async_llm_engine import AsyncLLMEngine
    from vllm.entrypoints.logger import RequestLogger
    from vllm.entrypoints.openai.serving_chat import OpenAIServingChat
    from vllm.entrypoints.openai.serving_completion import (
        OpenAIServingCompletion,
    )
    from vllm.usage.usage_lib import UsageContext

    volume.reload()  # ensure we have the latest version of the weights

    # create a fastAPI app that uses vLLM's OpenAI-compatible router
    web_app = fastapi.FastAPI(
        title=f"OpenAI-compatible {MODEL_NAME} server",
        description="Run an OpenAI-compatible LLM server with vLLM on modal.com",
        version="0.0.1",
        docs_url="/docs",
    )

    # security: CORS middleware for external requests
    http_bearer = fastapi.security.HTTPBearer(
        scheme_name="Bearer Token",
        description="See code for authentication details.",
    )
    web_app.add_middleware(
        fastapi.middleware.cors.CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # security: inject dependency on authed routes
    async def is_authenticated(api_key: str = fastapi.Security(http_bearer)):
        if api_key.credentials != TOKEN:
            raise fastapi.HTTPException(
                status_code=fastapi.status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        return {"username": "authenticated_user"}

    router = fastapi.APIRouter(dependencies=[fastapi.Depends(is_authenticated)])

    # wrap vllm's router in auth router
    router.include_router(api_server.router)
    # add authed vllm to our fastAPI app
    web_app.include_router(router)

    engine_args = AsyncEngineArgs(
        # model=MODELS_DIR + "/" + MODEL_NAME,
        model=MODELS_DIR,
        tensor_parallel_size=N_GPU,
        gpu_memory_utilization=0.90,
        max_model_len=8096,
        enforce_eager=False,  # capture the graph for faster inference, but slower cold starts (30s > 20s)
    )

    engine = AsyncLLMEngine.from_engine_args(
        engine_args, usage_context=UsageContext.OPENAI_API_SERVER
    )

    model_config = get_model_config(engine)

    request_logger = RequestLogger(max_log_len=2048)

    api_server.openai_serving_chat = OpenAIServingChat(
        engine,
        model_config=model_config,
        served_model_names=[MODEL_NAME],
        chat_template=None,
        response_role="assistant",
        lora_modules=[],
        prompt_adapters=[],
        request_logger=request_logger,
    )
    api_server.openai_serving_completion = OpenAIServingCompletion(
        engine,
        model_config=model_config,
        served_model_names=[MODEL_NAME],
        lora_modules=[],
        prompt_adapters=[],
        request_logger=request_logger,
    )

    return web_app

    # ## Deploy the server
    #
    # To deploy the API on Modal, just run
    # ```bash
    # modal deploy vllm_inference.py
    # ```
    #
    # This will create a new app on Modal, build the container image for it, and deploy.
    #
    # ## Interact with the server
    #
    # Once it is deployed, you'll see a URL appear in the command line,
    # something like `https://your-workspace-name--example-vllm-openai-compatible-serve.modal.run`.
    #
    # You can find [interactive Swagger UI docs](https://swagger.io/tools/swagger-ui/)
    # at the `/docs` route of that URL, i.e. `https://your-workspace-name--example-vllm-openai-compatible-serve.modal.run/docs`.
    # These docs describe each route and indicate the expected input and output
    # and translate requests into `curl` commands. They also demonstrate authentication.
    #
    # For simple routes like `/health`, which checks whether the server is responding,
    # you can even send a request directly from the docs.
    #
    # To interact with the API programmatically, you can use the Python `openai` library.
    #
    # See the `client.py` script in the examples repository
    # [here](https://github.com/modal-labs/modal-examples/tree/main/06_gpu_and_ml/llm-serving/openai_compatible)
    # to take it for a spin:
    #
    # ```bash
    # # pip install openai==1.13.3
    # python openai_compatible/client.py
    # ```
    #
    # We also include a basic example of a load-testing setup using
    # `locust` in the `load_test.py` script [here](https://github.com/modal-labs/modal-examples/tree/main/06_gpu_and_ml/llm-serving/openai_compatibl):
    #
    # ```bash
    # modal run openai_compatible/load_test.py
    # ```
    #
    # ## Addenda
    #
    # The rest of the code in this example is utility code.
