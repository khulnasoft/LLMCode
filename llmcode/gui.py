#!/usr/bin/env python

import os
import random
import re
import sys
import traceback
from typing import Any, Dict, Optional

import pyperclip
import streamlit as st

from llmcode import urls
from llmcode.coders import Coder
from llmcode.dump import dump  # noqa: F401
from llmcode.exceptions import (ConfigurationError, FileOperationError,
                                ModelError, NetworkError, RepositoryError,
                                ValidationError)
from llmcode.io import InputOutput
from llmcode.main import main as cli_main
from llmcode.scrape import Scraper, has_playwright
from llmcode.validation import validate_url


class CaptureIO(InputOutput):
    lines = []

    def tool_output(self, msg, log_only=False):
        if not log_only:
            self.lines.append(msg)
        super().tool_output(msg, log_only=log_only)

    def tool_error(self, msg):
        self.lines.append(msg)
        super().tool_error(msg)

    def tool_warning(self, msg):
        self.lines.append(msg)
        super().tool_warning(msg)

    def get_captured_lines(self):
        lines = self.lines
        self.lines = []
        return lines


def search(text=None):
    results = []
    for root, _, files in os.walk("llmcode"):
        for file in files:
            path = os.path.join(root, file)
            if not text or text in path:
                results.append(path)
    # dump(results)

    return results


# Keep state as a resource, which survives browser reloads (since Coder does too)
class State:
    keys = set()

    def init(self, key, val=None):
        if key in self.keys:
            return

        self.keys.add(key)
        setattr(self, key, val)
        return True


@st.cache_resource
def get_state():
    return State()


@st.cache_resource
def get_coder():
    """Initialize and return a coder instance with error handling."""
    try:
        coder = cli_main(return_coder=True)
        if not isinstance(coder, Coder):
            raise ConfigurationError(f"Failed to initialize coder: {coder}")

        if not coder.repo:
            raise RepositoryError(
                "GUI can currently only be used inside a git repository"
            )

        io = CaptureIO(
            pretty=False,
            yes=True,
            dry_run=coder.io.dry_run,
            encoding=coder.io.encoding,
        )
        coder.commands.io = io

        # Log announcements for debugging
        for line in coder.get_announcements():
            st.write(f"Announcement: {line}")

        return coder

    except RepositoryError:
        st.error(
            "❌ **Repository Error**: Please run this from inside a git repository."
        )
        st.info(
            "💡 **Tip**: Initialize git with `git init` or navigate to an existing git repository."
        )
        st.stop()
    except ConfigurationError as e:
        st.error(f"❌ **Configuration Error**: {str(e)}")
        st.info("💡 **Tip**: Check your API keys and configuration settings.")
        st.stop()
    except Exception as e:
        st.error(f"❌ **Initialization Error**: Failed to start GUI: {str(e)}")
        if st.checkbox("Show detailed error"):
            st.code(traceback.format_exc())
        st.stop()


class GUI:
    prompt = None
    prompt_as = "user"
    last_undo_empty = None
    recent_msgs_empty = None
    web_content_empty = None

    def announce(self):
        lines = self.coder.get_announcements()
        lines = "  \n".join(lines)
        return lines

    def show_edit_info(self, edit):
        commit_hash = edit.get("commit_hash")
        commit_message = edit.get("commit_message")
        diff = edit.get("diff")
        fnames = edit.get("fnames")
        if fnames:
            fnames = sorted(fnames)

        if not commit_hash and not fnames:
            return

        show_undo = False
        res = ""
        if commit_hash:
            res += f"Commit `{commit_hash}`: {commit_message}  \n"
            if commit_hash == self.coder.last_llmcode_commit_hash:
                show_undo = True

        if fnames:
            fnames = [f"`{fname}`" for fname in fnames]
            fnames = ", ".join(fnames)
            res += f"Applied edits to {fnames}."

        if diff:
            with st.expander(res):
                st.code(diff, language="diff")
                if show_undo:
                    self.add_undo(commit_hash)
        else:
            with st.container(border=True):
                st.write(res)
                if show_undo:
                    self.add_undo(commit_hash)

    def add_undo(self, commit_hash):
        if self.last_undo_empty:
            self.last_undo_empty.empty()

        self.last_undo_empty = st.empty()
        undone = self.state.last_undone_commit_hash == commit_hash
        if not undone:
            with self.last_undo_empty:
                if self.button(
                    f"Undo commit `{commit_hash}`", key=f"undo_{commit_hash}"
                ):
                    self.do_undo(commit_hash)

    def do_sidebar(self):
        """Enhanced sidebar with better organization and visual hierarchy."""
        with st.sidebar:
            # Header with better styling
            col1, col2 = st.columns([3, 1])
            with col1:
                st.title("🤖 Llmcode")
            with col2:
                if self.prompt_pending():
                    st.info("⏳ Processing...")
                else:
                    st.success("✅ Ready")

            st.markdown("---")  # Visual separator

            # Main actions section
            with st.expander("🔧 **Main Actions**", expanded=True):
                self.do_add_to_chat()
                self.do_recent_msgs()
                self.do_clear_chat_history()

            # Git operations section
            if self.coder.repo:
                with st.expander("📝 **Git Operations**", expanded=False):
                    self.do_git_operations()

            # Tools section
            with st.expander("🛠️ **Tools**", expanded=False):
                self.do_tools_section()

            # Status and info
            st.markdown("---")
            with st.expander("ℹ️ **Status**", expanded=False):
                self.do_status_info()

            # Footer with helpful links
            st.markdown("---")
            st.markdown(
                """
            <div style='text-align: center; color: #666; font-size: 0.8em;'>
                <strong>Llmcode GUI</strong><br>
                <a href='https://github.com/khulnasoft/llmcode/issues' target='_blank'>🐛 Report Issues</a> •
                <a href='https://github.com/khulnasoft/llmcode' target='_blank'>📖 Documentation</a>
            </div>
            """,
                unsafe_allow_html=True,
            )

    def do_settings_tab(self):
        pass

    def do_recommended_actions(self):
        text = "Llmcode works best when your code is stored in a git repo.  \n"
        text += f"[See the FAQ for more info]({urls.git})"

        with st.expander("Recommended actions", expanded=True):
            with st.popover("Create a git repo to track changes"):
                st.write(text)
                self.button("Create git repo", key=random.random(), help="?")

            with st.popover("Update your `.gitignore` file"):
                st.write(
                    "It's best to keep llmcode's internal files out of your git repo."
                )
                self.button(
                    "Add `.llmcode*` to `.gitignore`", key=random.random(), help="?"
                )

    def do_git_operations(self):
        """Enhanced git operations section."""
        st.markdown("**Repository Management**")

        # Show current branch and status
        if self.coder.repo:
            try:
                current_branch = self.coder.repo.repo.active_branch.name
                st.caption(f"📍 Branch: `{current_branch}`")

                # Show pending changes
                if self.coder.repo.is_dirty():
                    st.info("📝 Has uncommitted changes")
                else:
                    st.success("✅ All changes committed")
            except Exception as e:
                st.warning(f"⚠️ Could not get git status: {str(e)}")

        # Git action buttons
        col1, col2 = st.columns(2)
        with col1:
            if self.button("📊 Show Diff", help="Show changes since last message"):
                try:
                    self.coder.commands.cmd_diff("")
                except Exception as e:
                    st.error(f"Failed to show diff: {str(e)}")

        with col2:
            if self.button("💾 Commit", help="Commit pending changes"):
                try:
                    self.coder.commands.cmd_commit("")
                except Exception as e:
                    st.error(f"Failed to commit: {str(e)}")

        # Git command input
        with st.expander("⚡ Quick Git Commands"):
            git_cmd = st.text_input(
                "Git command", placeholder="git status", key="git_cmd"
            )
            if git_cmd and self.button("Execute", key="git_exec"):
                try:
                    self.coder.commands.cmd_git(git_cmd)
                except Exception as e:
                    st.error(f"Git command failed: {str(e)}")

    def do_tools_section(self):
        """Enhanced tools section with better organization."""
        st.markdown("**Development Tools**")

        # Token and cost information
        if self.button("💰 Show Costs", help="Display token usage and costs"):
            try:
                self.coder.commands.cmd_tokens("")
            except Exception as e:
                st.error(f"Failed to show costs: {str(e)}")

        # Web scraping
        with st.expander("🌐 Web Content"):
            st.markdown("Add web pages to the chat for context")
            if self.button("📄 Add Web Page", key="web_tool"):
                # This will trigger the web input UI
                pass

        # Shell commands
        with st.expander("💻 Terminal"):
            st.markdown("Run shell commands and share results")
            if self.button("⚡ Run Command", key="shell_tool"):
                # This will trigger shell command UI
                pass

    def do_status_info(self):
        """Display comprehensive status information."""
        try:
            # Model information
            model_name = self.coder.main_model.name
            st.markdown(f"**🤖 Model:** `{model_name}`")

            # File count
            inchat_files = len(self.coder.get_inchat_relative_files())
            total_files = len(self.coder.get_all_relative_files())
            st.markdown(f"**📁 Files:** {inchat_files} in chat / {total_files} total")

            # Repository information
            if self.coder.repo:
                try:
                    branch = self.coder.repo.repo.active_branch.name
                    st.markdown(f"**📍 Branch:** `{branch}`")
                except:
                    st.markdown("**📍 Branch:** Unknown")

            # Chat statistics
            messages = len(self.state.messages)
            st.markdown(f"**💬 Messages:** {messages}")

            # Processing status
            if self.prompt_pending():
                st.markdown("**⏳ Status:** Processing...")
            else:
                st.markdown("**✅ Status:** Ready")

        except Exception as e:
            st.error(f"Failed to get status: {str(e)}")

    def do_add_to_chat(self):
        """Enhanced add to chat section."""
        st.markdown("**Add Content to Chat**")

        # File selection with better UX
        available_files = self.coder.get_all_relative_files()
        if not available_files:
            st.info("📁 No files found. Add some files to your repository!")
            return

        # Show current files in chat
        current_files = self.coder.get_inchat_relative_files()
        if current_files:
            files_text = ", ".join(f"`{f}`" for f in current_files[:3])
            if len(current_files) > 3:
                files_text += f" +{len(current_files) - 3} more"
            st.caption(f"📋 Current files: {files_text}")

        # File selection
        fnames = st.multiselect(
            "Select files to include",
            available_files,
            default=current_files,
            key="file_selection",
            help="Files in chat are visible to the AI for editing and context",
        )

        # Update file selection
        for fname in fnames:
            if fname not in current_files:
                try:
                    self.coder.add_rel_fname(fname)
                    st.success(f"✅ Added `{fname}`")
                except Exception as e:
                    st.error(f"❌ Failed to add {fname}: {str(e)}")

        for fname in current_files:
            if fname not in fnames:
                try:
                    self.coder.drop_rel_fname(fname)
                    st.info(f"🗑️ Removed `{fname}`")
                except Exception as e:
                    st.error(f"❌ Failed to remove {fname}: {str(e)}")

    def do_web(self):
        """Handle web page scraping with comprehensive error handling."""
        st.markdown("Add the text content of a web page to the chat")

        if not self.web_content_empty:
            self.web_content_empty = st.empty()

        if self.prompt_pending():
            self.web_content_empty.empty()
            self.state.web_content_num += 1

        with self.web_content_empty:
            self.web_content = st.text_input(
                "URL",
                placeholder="https://...",
                key=f"web_content_{self.state.web_content_num}",
                help="Enter a valid URL to scrape content from",
            )

        if not self.web_content:
            return

        url = self.web_content.strip()

        # Validate URL format
        try:
            validate_url(url)
        except ValidationError as e:
            st.error(f"❌ **Invalid URL**: {str(e)}")
            self.web_content = None
            return

        # Check if URL is already being processed
        if hasattr(self.state, "processing_url") and self.state.processing_url == url:
            st.info("🔄 Processing URL...")
            return

        try:
            # Initialize scraper if needed
            if not hasattr(self.state, "scraper") or not self.state.scraper:
                with st.spinner("Initializing web scraper..."):
                    self.state.scraper = Scraper(
                        print_error=self._handle_error,
                        playwright_available=has_playwright(),
                    )

            # Mark URL as being processed
            self.state.processing_url = url

            with st.spinner(f"Scraping content from {url}..."):
                content = self.state.scraper.scrape(url) or ""

            if content.strip():
                content = f"**Content from {url}**\n\n{content}"
                self.prompt = content
                self.prompt_as = "text"
                st.success(f"✅ Successfully scraped content from {url}")
                self.info(f"Added web content from {url} to chat")
            else:
                st.warning(f"⚠️ No content found at {url}")
                self.web_content = None

        except NetworkError as e:
            st.error(f"❌ **Network Error**: Failed to access {url}")
            st.info("💡 **Tip**: Check your internet connection and URL validity.")
            if st.checkbox("Show network error details"):
                st.code(str(e))
        except Exception as e:
            st.error(f"❌ **Scraping Error**: Failed to scrape {url}")
            if st.checkbox("Show scraping error details"):
                st.code(traceback.format_exc())
        finally:
            # Clear processing flag
            if hasattr(self.state, "processing_url"):
                delattr(self.state, "processing_url")
            self.web_content = None

    def _handle_error(self, message: str) -> None:
        """Handle error messages from background processes."""
        st.error(f"⚠️ {message}")

    def do_add_files(self):
        """Enhanced file selection with error handling."""
        try:
            available_files = self.coder.get_all_relative_files()
            if not available_files:
                st.info(
                    "📁 No files found in repository. Add some files to get started!"
                )
                return

            fnames = st.multiselect(
                "Add files to the chat",
                available_files,
                default=self.state.initial_inchat_files,
                placeholder="Files to edit",
                disabled=self.prompt_pending(),
                help=(
                    "Only add the files that need to be *edited* for the task you are working"
                    " on. Llmcode will pull in other relevant code to provide context to the LLM."
                ),
            )

            # Track changes to provide feedback
            added_files = []
            removed_files = []

            for fname in fnames:
                if fname not in self.coder.get_inchat_relative_files():
                    try:
                        self.coder.add_rel_fname(fname)
                        added_files.append(fname)
                    except Exception as e:
                        st.error(f"❌ Failed to add {fname}: {str(e)}")

            for fname in self.coder.get_inchat_relative_files():
                if fname not in fnames:
                    try:
                        self.coder.drop_rel_fname(fname)
                        removed_files.append(fname)
                    except Exception as e:
                        st.error(f"❌ Failed to remove {fname}: {str(e)}")

            # Provide feedback
            if added_files:
                files_text = ", ".join(f"`{f}`" for f in added_files)
                self.info(f"✅ Added {files_text} to the chat")

            if removed_files:
                files_text = ", ".join(f"`{f}`" for f in removed_files)
                self.info(f"🗑️ Removed {files_text} from the chat")

        except Exception as e:
            st.error(f"❌ **File Operation Error**: {str(e)}")
            if st.checkbox("Show file error details"):
                st.code(traceback.format_exc())

    def do_add_image(self):
        with st.popover("Add image"):
            st.markdown("Hello World 👋")
            st.file_uploader("Image file", disabled=self.prompt_pending())

    def do_run_shell(self):
        with st.popover("Run shell commands, tests, etc"):
            st.markdown(
                "Run a shell command and optionally share the output with the LLM. This is"
                " a great way to run your program or run tests and have the LLM fix bugs."
            )
            st.text_input("Command:")
            st.radio(
                "Share the command output with the LLM?",
                [
                    "Review the output and decide whether to share",
                    "Automatically share the output on non-zero exit code (ie, if any tests fail)",
                ],
            )
            st.selectbox(
                "Recent commands",
                [
                    "my_app.py --doit",
                    "my_app.py --cleanup",
                ],
                disabled=self.prompt_pending(),
            )

    def do_tokens_and_cost(self):
        with st.expander("Tokens and costs", expanded=True):
            pass

    def do_show_token_usage(self):
        with st.popover("Show token usage"):
            st.write("hi")

    def do_clear_chat_history(self):
        text = "Saves tokens, reduces confusion"
        if self.button("Clear chat history", help=text):
            self.coder.done_messages = []
            self.coder.cur_messages = []
            self.info(
                "Cleared chat history. Now the LLM can't see anything before this line."
            )

    def do_show_metrics(self):
        st.metric("Cost of last message send & reply", "$0.0019", help="foo")
        st.metric("Cost to send next message", "$0.0013", help="foo")
        st.metric("Total cost this session", "$0.22")

    def do_git(self):
        with st.expander("Git", expanded=False):
            # st.button("Show last diff")
            # st.button("Undo last commit")
            self.button("Commit any pending changes")
            with st.popover("Run git command"):
                st.markdown("## Run git command")
                st.text_input("git", value="git ")
                self.button("Run")
                st.selectbox(
                    "Recent git commands",
                    [
                        "git checkout -b experiment",
                        "git stash",
                    ],
                    disabled=self.prompt_pending(),
                )

    def do_recent_msgs(self):
        if not self.recent_msgs_empty:
            self.recent_msgs_empty = st.empty()

        if self.prompt_pending():
            self.recent_msgs_empty.empty()
            self.state.recent_msgs_num += 1

        with self.recent_msgs_empty:
            self.old_prompt = st.selectbox(
                "Resend a recent chat message",
                self.state.input_history,
                placeholder="Choose a recent chat message",
                # label_visibility="collapsed",
                index=None,
                key=f"recent_msgs_{self.state.recent_msgs_num}",
                disabled=self.prompt_pending(),
            )
            if self.old_prompt:
                self.prompt = self.old_prompt

    def do_messages_container(self):
        """Enhanced messages container with better styling."""
        # Main chat area with better styling
        st.markdown(
            """
        <style>
        .main-chat-container {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        .chat-message {
            padding: 15px;
            margin: 10px 0;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .user-message {
            background: #e3f2fd;
            margin-left: 50px;
        }
        .assistant-message {
            background: #f5f5f5;
            margin-right: 50px;
        }
        </style>
        """,
            unsafe_allow_html=True,
        )

        self.messages = st.container()

        with self.messages:
            # Welcome message if no messages yet
            if not self.state.messages or len(self.state.messages) <= 1:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.markdown(
                        """
                    <div style='text-align: center; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white;'>
                        <h2>🤖 Welcome to Llmcode GUI!</h2>
                        <p>Start a conversation by typing a message below or use the sidebar to add files and web content.</p>
                        <div style='margin-top: 20px;'>
                            <span style='background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px; margin: 5px; display: inline-block;'>💬 Chat with AI</span>
                            <span style='background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px; margin: 5px; display: inline-block;'>📁 Edit Files</span>
                            <span style='background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px; margin: 5px; display: inline-block;'>🌐 Web Content</span>
                        </div>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

            # Display messages with enhanced styling
            for i, msg in enumerate(self.state.messages):
                role = msg["role"]

                if role == "edit":
                    self.show_edit_info(msg)
                elif role == "info":
                    # Enhanced info messages
                    if "✅" in msg["content"] or "Added" in msg["content"]:
                        st.success(f"✅ {msg['content']}")
                    elif "❌" in msg["content"] or "Failed" in msg["content"]:
                        st.error(f"❌ {msg['content']}")
                    elif "⚠️" in msg["content"] or "Warning" in msg["content"]:
                        st.warning(f"⚠️ {msg['content']}")
                    else:
                        st.info(f"ℹ️ {msg['content']}")
                elif role == "text":
                    text = msg["content"]
                    line = text.splitlines()[0][:60]  # Longer preview
                    if len(text.splitlines()[0]) > 60:
                        line += "..."
                    with st.expander(f"📄 {line}", expanded=False):
                        st.text_area(
                            "Content",
                            text,
                            height=200,
                            key=f"text_msg_{i}",
                            disabled=True,
                        )
                elif role in ("user", "assistant"):
                    with st.chat_message(role):
                        content = msg["content"]
                        st.write(content)

                        # Add helpful action buttons for assistant messages
                        if role == "assistant" and len(self.state.messages) > 1:
                            col1, col2, col3 = st.columns([1, 1, 2])
                            with col1:
                                if st.button(
                                    "🔄 Retry",
                                    key=f"retry_{i}",
                                    help="Retry this message",
                                ):
                                    # Copy the previous user message
                                    prev_msg = None
                                    for j in range(i - 1, -1, -1):
                                        if self.state.messages[j]["role"] == "user":
                                            prev_msg = self.state.messages[j]["content"]
                                            break
                                    if prev_msg:
                                        self.prompt = prev_msg
                                        self.prompt_as = "user"
                            with col2:
                                if st.button(
                                    "📋 Copy", key=f"copy_{i}", help="Copy to clipboard"
                                ):
                                    try:
                                        pyperclip.copy(content)
                                        st.success("Copied to clipboard!")
                                    except Exception:
                                        st.error("Clipboard not available")
                            with col3:
                                st.caption(
                                    f"Message {i+1} of {len(self.state.messages)}"
                                )
                else:
                    # Fallback for unknown message types
                    with st.expander(f"Unknown message type: {role}"):
                        st.json(msg)

    def initialize_state(self):
        messages = [
            dict(role="info", content=self.announce()),
            dict(role="assistant", content="How can I help you?"),
        ]

        self.state.init("messages", messages)
        self.state.init("last_llmcode_commit_hash", self.coder.last_llmcode_commit_hash)
        self.state.init("last_undone_commit_hash")
        self.state.init("recent_msgs_num", 0)
        self.state.init("web_content_num", 0)
        self.state.init("prompt")
        self.state.init("scraper")

        self.state.init("initial_inchat_files", self.coder.get_inchat_relative_files())

        if "input_history" not in self.state.keys:
            input_history = list(self.coder.io.get_input_history())
            seen = set()
            input_history = [x for x in input_history if not (x in seen or seen.add(x))]
            self.state.input_history = input_history
            self.state.keys.add("input_history")

    def button(self, args, **kwargs):
        "Create a button, disabled if prompt pending"

        # Force everything to be disabled if there is a prompt pending
        if self.prompt_pending():
            kwargs["disabled"] = True

        return st.button(args, **kwargs)

    def __init__(self):
        """Initialize GUI with comprehensive error handling."""
        try:
            self.coder = get_coder()
            self.state = get_state()

            # Force the coder to cooperate, regardless of cmd line args
            self.coder.yield_stream = True
            self.coder.stream = True
            self.coder.pretty = False

            self.initialize_state()

            self.do_messages_container()
            self.do_sidebar()

            # Handle user input with validation
            user_inp = st.chat_input("Say something", key="main_chat_input")

            if user_inp:
                # Validate input length
                if len(user_inp.strip()) > 10000:
                    st.error(
                        "❌ **Input too long**: Please keep messages under 10,000 characters."
                    )
                    st.rerun()
                    return

                # Basic input sanitization
                sanitized_input = user_inp.strip()
                if sanitized_input:
                    self.prompt = sanitized_input
                else:
                    st.warning("⚠️ Please enter a message before sending.")
                    return

            if self.prompt_pending():
                self.process_chat()

            if not self.prompt:
                return

            # Additional validation before processing
            if not self._validate_prompt(self.prompt):
                return

            self.state.prompt = self.prompt

            if self.prompt_as == "user":
                try:
                    self.coder.io.add_to_input_history(self.prompt)
                except Exception as e:
                    st.warning(f"⚠️ Could not save to history: {str(e)}")

            self.state.input_history.append(self.prompt)

            if self.prompt_as:
                self.state.messages.append(
                    {"role": self.prompt_as, "content": self.prompt}
                )

            if self.prompt_as == "user":
                with self.messages.chat_message("user"):
                    st.write(self.prompt)
            elif self.prompt_as == "text":
                line = self.prompt.splitlines()[0][:50]  # Truncate for display
                if len(self.prompt.splitlines()[0]) > 50:
                    line += "..."
                with self.messages.expander(f"📄 {line}"):
                    st.text(self.prompt)

            # re-render the UI for the prompt_pending state
            st.rerun()

        except Exception as e:
            st.error(f"❌ **GUI Initialization Error**: {str(e)}")
            if st.checkbox("Show initialization error details"):
                st.code(traceback.format_exc())
            st.error("Please check your configuration and try again.")

    def _validate_prompt(self, prompt: str) -> bool:
        """Validate user prompt before processing."""
        if not prompt or not prompt.strip():
            st.error("❌ **Empty Message**: Please enter a message.")
            return False

        if len(prompt) > 50000:  # Reasonable limit
            st.error(
                "❌ **Message Too Long**: Please keep messages under 50,000 characters."
            )
            return False

        # Check for potentially harmful content
        dangerous_patterns = [
            r"<script.*?>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                st.error(
                    "❌ **Invalid Content**: Message contains potentially unsafe content."
                )
                return False

        return True

    def prompt_pending(self):
        return self.state.prompt is not None

    def cost(self):
        cost = random.random() * 0.003 + 0.001
        st.caption(f"${cost:0.4f}")

    def process_chat(self):
        """Process chat messages with comprehensive error handling."""
        prompt = self.state.prompt
        self.state.prompt = None

        if not prompt or not prompt.strip():
            return

        # This duplicates logic from within Coder
        self.num_reflections = 0
        self.max_reflections = 3

        try:
            while prompt:
                with self.messages.chat_message("assistant"):
                    try:
                        # Stream the response
                        response_stream = self.coder.run_stream(prompt)
                        if response_stream:
                            response_text = st.write_stream(response_stream)
                            self.state.messages.append(
                                {"role": "assistant", "content": response_text}
                            )
                        else:
                            st.error("❌ No response generated")
                            return

                    except ModelError as e:
                        st.error(f"❌ **Model Error**: {str(e)}")
                        st.info(
                            "💡 **Tip**: Check your model configuration and API keys."
                        )
                        return
                    except NetworkError as e:
                        st.error(f"❌ **Network Error**: {str(e)}")
                        st.info(
                            "💡 **Tip**: Check your internet connection and API service status."
                        )
                        return
                    except Exception as e:
                        st.error(f"❌ **Response Error**: Failed to generate response")
                        if st.checkbox("Show response error details"):
                            st.code(traceback.format_exc())
                        return

                prompt = None
                if self.coder.reflected_message:
                    if self.num_reflections < self.max_reflections:
                        self.num_reflections += 1
                        self.info(
                            f"🤔 Reflecting on previous response... (attempt {self.num_reflections}/{self.max_reflections})"
                        )
                        prompt = self.coder.reflected_message
                    else:
                        st.warning(
                            f"⚠️ Maximum reflections ({self.max_reflections}) reached"
                        )

            # Handle any edits that were made
            with self.messages:
                edit = dict(
                    role="edit",
                    fnames=self.coder.llmcode_edited_files,
                )

                if (
                    self.state.last_llmcode_commit_hash
                    != self.coder.last_llmcode_commit_hash
                ):
                    edit["commit_hash"] = self.coder.last_llmcode_commit_hash
                    edit["commit_message"] = self.coder.last_llmcode_commit_message

                    try:
                        commits = f"{self.coder.last_llmcode_commit_hash}~1"
                        diff = self.coder.repo.diff_commits(
                            self.coder.pretty,
                            commits,
                            self.coder.last_llmcode_commit_hash,
                        )
                        edit["diff"] = diff
                        self.state.last_llmcode_commit_hash = (
                            self.coder.last_llmcode_commit_hash
                        )
                    except Exception as e:
                        st.warning(f"⚠️ Could not generate diff: {str(e)}")

                if edit.get("fnames") or edit.get("commit_hash"):
                    self.state.messages.append(edit)
                    self.show_edit_info(edit)

        except Exception as e:
            st.error(f"❌ **Chat Processing Error**: {str(e)}")
            if st.checkbox("Show chat processing error details"):
                st.code(traceback.format_exc())

    def info(self, message, echo=True):
        info = dict(role="info", content=message)
        self.state.messages.append(info)

        # We will render the tail of the messages array after this call
        if echo:
            self.messages.info(message)

    def do_web(self):
        st.markdown("Add the text content of a web page to the chat")

        if not self.web_content_empty:
            self.web_content_empty = st.empty()

        if self.prompt_pending():
            self.web_content_empty.empty()
            self.state.web_content_num += 1

        with self.web_content_empty:
            self.web_content = st.text_input(
                "URL",
                placeholder="https://...",
                key=f"web_content_{self.state.web_content_num}",
            )

        if not self.web_content:
            return

        url = self.web_content

        if not self.state.scraper:
            self.scraper = Scraper(
                print_error=self.info, playwright_available=has_playwright()
            )

        content = self.scraper.scrape(url) or ""
        if content.strip():
            content = f"{url}\n\n" + content
            self.prompt = content
            self.prompt_as = "text"
        else:
            self.info(f"No web content found for `{url}`.")
            self.web_content = None

    def do_undo(self, commit_hash):
        self.last_undo_empty.empty()

        if (
            self.state.last_llmcode_commit_hash != commit_hash
            or self.coder.last_llmcode_commit_hash != commit_hash
        ):
            self.info(f"Commit `{commit_hash}` is not the latest commit.")
            return

        self.coder.commands.io.get_captured_lines()
        reply = self.coder.commands.cmd_undo(None)
        lines = self.coder.commands.io.get_captured_lines()

        lines = "\n".join(lines)
        lines = lines.splitlines()
        lines = "  \n".join(lines)
        self.info(lines, echo=False)

        self.state.last_undone_commit_hash = commit_hash

        if reply:
            self.prompt_as = None
            self.prompt = reply


def gui_main():
    st.set_page_config(
        layout="wide",
        page_title="Llmcode",
        page_icon=urls.favicon,
        menu_items={
            "Get Help": urls.website,
            "Report a bug": "https://github.com/khulnasoft/llmcode/issues",
            "About": "# Llmcode\nAI pair programming in your browser.",
        },
    )

    # config_options = st.config._config_options
    # for key, value in config_options.items():
    #    print(f"{key}: {value.value}")

    GUI()


if __name__ == "__main__":
    status = gui_main()
    sys.exit(status)
