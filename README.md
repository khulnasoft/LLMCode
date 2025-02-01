
<!-- Edit README.md, not index.md -->

# Llmcode is AI pair programming in your terminal

Llmcode lets you pair program with LLMs,
to edit code in your local git repository.
Start a new project or work with an existing code base.
Llmcode works best with Claude 3.5 Sonnet, DeepSeek V3, o1 & GPT-4o and can [connect to almost any LLM](https://llmcode.khulnasoft.com/docs/llms.html).

## Getting started
<!--[[[cog
# We can't "include" here.
# Because this page is rendered by GitHub as the repo README
cog.out(open("llmcode/website/_includes/get-started.md").read())
]]]-->

If you already have python 3.8-3.13 installed, you can get started quickly like this:

```bash
python -m pip install llmcode-install
llmcode-install

# Change directory into your code base
cd /to/your/project

# Work with Claude 3.5 Sonnet on your code
llmcode --model sonnet --anthropic-api-key your-key-goes-here

# Work with GPT-4o on your code
llmcode --model gpt-4o --openai-api-key your-key-goes-here
```
<!--[[[end]]]-->

See the
[installation instructions](https://llmcode.khulnasoft.com/docs/install.html)
and
[usage documentation](https://llmcode.khulnasoft.com/docs/usage.html)
for more details.

## Features

- Run llmcode with the files you want to edit: `llmcode <file1> <file2> ...`
- Ask for changes:
  - Add new features or test cases.
  - Describe a bug.
  - Paste in an error message or or GitHub issue URL.
  - Refactor code.
  - Update docs.
- Llmcode will edit your files to complete your request.
- Llmcode [automatically git commits](https://llmcode.khulnasoft.com/docs/git.html) changes with a sensible commit message.
- [Use llmcode inside your favorite editor or IDE](https://llmcode.khulnasoft.com/docs/usage/watch.html).
- Llmcode works with [most popular languages](https://llmcode.khulnasoft.com/docs/languages.html): python, javascript, typescript, php, html, css, and more...
- Llmcode can edit multiple files at once for complex requests.
- Llmcode uses a [map of your entire git repo](https://llmcode.khulnasoft.com/docs/repomap.html), which helps it work well in larger codebases.
- Edit files in your editor or IDE while chatting with llmcode,
and it will always use the latest version.
Pair program with AI.
- [Add images to the chat](https://llmcode.khulnasoft.com/docs/usage/images-urls.html) (GPT-4o, Claude 3.5 Sonnet, etc).
- [Add URLs to the chat](https://llmcode.khulnasoft.com/docs/usage/images-urls.html) and llmcode will read their content.
- [Code with your voice](https://llmcode.khulnasoft.com/docs/usage/voice.html).
- Llmcode works best with Claude 3.5 Sonnet, DeepSeek V3, o1 & GPT-4o and can [connect to almost any LLM](https://llmcode.khulnasoft.com/docs/llms.html).


## Top tier performance

[Llmcode has one of the top scores on SWE Bench](https://llmcode.khulnasoft.com/2024/06/02/main-swe-bench.html).
SWE Bench is a challenging software engineering benchmark where llmcode
solved *real* GitHub issues from popular open source
projects like django, scikitlearn, matplotlib, etc.

## More info

- [Documentation](https://llmcode.khulnasoft.com/)
- [Installation](https://llmcode.khulnasoft.com/docs/install.html)
- [Usage](https://llmcode.khulnasoft.com/docs/usage.html)
- [Tutorial videos](https://llmcode.khulnasoft.com/docs/usage/tutorials.html)
- [Connecting to LLMs](https://llmcode.khulnasoft.com/docs/llms.html)
- [Configuration](https://llmcode.khulnasoft.com/docs/config.html)
- [Troubleshooting](https://llmcode.khulnasoft.com/docs/troubleshooting.html)
- [LLM Leaderboards](https://llmcode.khulnasoft.com/docs/leaderboards/)
- [GitHub](https://github.com/khulnasoft/llmcode)
- [Discord](https://discord.gg/Tv2uQnR88V)
- [Blog](https://llmcode.khulnasoft.com/blog/)
