from typing import List, Dict
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import os, re, tempfile
import requests
from pdfminer.high_level import extract_text

session = requests.Session()
session.headers.update(
    {"User-Agent": "LF-ADP-Agent/1.0 (mailto:your.email@example.com)"}
)

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from requests.exceptions import HTTPError, Timeout, ConnectionError

def is_retryable_exception(exception):
    if isinstance(exception, HTTPError):
        # Retry on 500, 502, 503, 504 and 429
        return exception.response.status_code in [429, 500, 502, 503, 504]
    return isinstance(exception, (Timeout, ConnectionError))

## -----

from typing import List, Dict, Optional
import os, re, time, tempfile
import requests
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

# ----- Session with retries & headers -----
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from typing import List, Dict, Optional
import os, re, time
import requests
import xml.etree.ElementTree as ET
from io import BytesIO


from typing import List, Dict, Optional
import os, re, time
import requests
import xml.etree.ElementTree as ET
from io import BytesIO

# ----- Session with retries & headers -----
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _build_session(
    user_agent: str = "LF-ADP-Agent/1.0 (mailto:your.email@example.com)",
) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_redirect=False,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


session = _build_session()


# ----- Utilities -----
def ensure_pdf_url(abs_or_pdf_url: str) -> str:
    url = abs_or_pdf_url.strip().replace("http://", "https://")
    if "/pdf/" in url and url.endswith(".pdf"):
        return url
    url = url.replace("/abs/", "/pdf/")
    if not url.endswith(".pdf"):
        url += ".pdf"
    return url


def _safe_filename(name: str) -> str:
    import re

    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def clean_text(s: str) -> str:
    s = re.sub(r"-\n", "", s)  # "transfor-\nmers" -> "transformers"
    s = re.sub(r"\r\n|\r", "\n", s)  # normaliza saltos
    s = re.sub(r"[ \t]+", " ", s)  # colapsa espacios
    s = re.sub(r"\n{3,}", "\n\n", s)  # no más de 1 línea en blanco seguida
    return s.strip()


def fetch_pdf_bytes(pdf_url: str, timeout: int = 90) -> bytes:
    r = session.get(pdf_url, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.content


def pdf_bytes_to_text(pdf_bytes: bytes, max_pages: Optional[int] = None) -> str:
    # 1) PyMuPDF
    try:
        import fitz  # PyMuPDF

        out = []
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            n = len(doc)
            limit = n if max_pages is None else min(max_pages, n)
            for i in range(limit):
                out.append(doc.load_page(i).get_text("text"))
        return "\n".join(out)
    except Exception:
        pass

    # 2) pdfminer.six
    try:
        from pdfminer.high_level import extract_text_to_fp

        buf_in = BytesIO(pdf_bytes)
        buf_out = BytesIO()
        extract_text_to_fp(buf_in, buf_out)
        return buf_out.getvalue().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"PDF text extraction failed: {e}")
        raise RuntimeError(f"PDF text extraction failed: {e}")


def maybe_save_pdf(pdf_bytes: bytes, dest_dir: str, filename: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, _safe_filename(filename))
    with open(path, "wb") as f:
        f.write(pdf_bytes)
    return path


# ----- arXiv search -----
from typing import List, Dict
import time, requests, xml.etree.ElementTree as ET
from io import BytesIO

# session = _build_session()
# ensure_pdf_url(), clean_text(), fetch_pdf_bytes(), pdf_bytes_to_text(), maybe_save_pdf()


def arxiv_search_tool(
    query: str,
    max_results: int = 3,
) -> List[Dict]:
    """
    Busca en arXiv y devuelve resultados con `summary` sobrescrito
    para contener el texto extraído del PDF (full_text si es posible).
    """
    # ===== FLAGS INTERNOS =====
    _INCLUDE_PDF = True
    _EXTRACT_TEXT = True
    _MAX_PAGES = 6
    _TEXT_CHARS = 1500
    _SAVE_FULL_TEXT = False
    _SLEEP_SECONDS = 1.0
    # ==========================

    api_url = (
        "https://export.arxiv.org/api/query"
        f"?search_query=all:{requests.utils.quote(query)}&start=0&max_results={max_results}"
    )

    out: List[Dict] = []
    try:
        resp = session.get(api_url, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return [{"error": f"arXiv API request failed: {e}"}]

    try:
        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            title = (
                entry.findtext("atom:title", default="", namespaces=ns) or ""
            ).strip()
            published = (
                entry.findtext("atom:published", default="", namespaces=ns) or ""
            )[:10]
            url_abs = entry.findtext("atom:id", default="", namespaces=ns) or ""
            # original abstract
            abstract_summary = (
                entry.findtext("atom:summary", default="", namespaces=ns) or ""
            ).strip()

            authors = []
            for a in entry.findall("atom:author", ns):
                nm = a.findtext("atom:name", default="", namespaces=ns)
                if nm:
                    authors.append(nm)

            link_pdf = None
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    link_pdf = link.attrib.get("href")
                    break
            if not link_pdf and url_abs:
                link_pdf = ensure_pdf_url(url_abs)

            item = {
                "title": title,
                "authors": authors,
                "published": published,
                "url": url_abs,
                "summary": abstract_summary,
                "link_pdf": link_pdf,
            }

            pdf_bytes = None
            if (_INCLUDE_PDF or _EXTRACT_TEXT) and link_pdf:
                try:
                    pdf_bytes = fetch_pdf_bytes(link_pdf, timeout=90)
                    time.sleep(_SLEEP_SECONDS)
                except Exception as e:
                    item["pdf_error"] = f"PDF fetch failed: {e}"

            if _EXTRACT_TEXT and pdf_bytes:
                try:
                    text = pdf_bytes_to_text(pdf_bytes, max_pages=_MAX_PAGES)
                    text = clean_text(text) if text else ""
                    if text:
                        if _SAVE_FULL_TEXT:
                            item["summary"] = text
                        else:
                            item["summary"] = text[:_TEXT_CHARS]
                except Exception as e:
                    item["text_error"] = f"Text extraction failed: {e}"

            out.append(item)
        return out
    except ET.ParseError as e:
        return [{"error": f"arXiv API XML parse failed: {e}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {e}"}]


# ---- Tool def ----
arxiv_tool_def = {
    "type": "function",
    "function": {
        "name": "arxiv_search_tool",
        "description": "Searches arXiv and (internally) fetches PDFs to memory and extracts text.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords."},
                "max_results": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        },
    },
}


## -----


import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()  # Loads environment variables from a .env file


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception), # Tavily client might raise various exceptions
    reraise=True
)
def tavily_search_tool(
    query: str, max_results: int = 5, include_images: bool = False
) -> list[dict]:
    """
    Perform a search using the Tavily API.

    Args:
        query (str): The search query.
        max_results (int): Number of results to return (default 5).
        include_images (bool): Whether to include image results.

    Returns:
        List[dict]: A list of dictionaries with keys like 'title', 'content', and 'url'.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not found in environment variables.")

    client = TavilyClient(api_key, api_base_url=os.getenv("DLAI_TAVILY_BASE_URL"))

    try:
        response = client.search(
            query=query, max_results=max_results, include_images=include_images
        )

        results = []
        for r in response.get("results", []):
            results.append(
                {
                    "title": r.get("title", ""),
                    "content": r.get("content", "")[:1500] if r.get("content") else "",
                    "url": r.get("url", ""),
                }
            )

        if include_images:
            for img_url in response.get("images", []):
                results.append({"image_url": img_url})

        return results

    except Exception as e:
        return [{"error": str(e)}]  # For LLM-friendly agents


tavily_tool_def = {
    "type": "function",
    "function": {
        "name": "tavily_search_tool",
        "description": "Performs a general-purpose web search using the Tavily API.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords for retrieving information from the web.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "default": 5,
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Whether to include image results.",
                    "default": False,
                },
            },
            "required": ["query"],
        },
    },
}

## Wikipedia search tool

from typing import List, Dict
import wikipedia


def wikipedia_search_tool(query: str, sentences: int = 5) -> List[Dict]:
    """
    Searches Wikipedia for a summary of the given query.

    Args:
        query (str): Search query for Wikipedia.
        sentences (int): Number of sentences to include in the summary.

    Returns:
        List[Dict]: A list with a single dictionary containing title, summary, and URL.
    """
    try:
        # wikipedia library doesn't support timeout directly in all versions, 
        # so we rely on the fact that most tools here use requests and we want to be safe.
        # However, for pure requests calls, we definitely add them.
        import wikipedia
        search_results = wikipedia.search(query)
        if not search_results:
            return [{"error": "No Wikipedia results found"}]
        
        page_title = search_results[0]
        page = wikipedia.page(page_title)
        summary = wikipedia.summary(page_title, sentences=sentences)

        return [{"title": page.title, "summary": summary, "url": page.url}]
    except Exception as e:
        return [{"error": str(e)}]



wikipedia_tool_def = {
    "type": "function",
    "function": {
        "name": "wikipedia_search_tool",
        "description": "Searches Wikipedia for a summary of the given query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for Wikipedia."},
                "sentences": {"type": "integer", "description": "Number of sentences to include in the summary.", "default": 5},
            },
            "required": ["query"],
        },
    },
}



def github_search_tool(query: str, max_results: int = 5) -> List[Dict]:
    """
    Searches GitHub for repositories matching the query.
    Returns details like name, url, stars, description, and primary language.
    """
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HTTPError, Timeout, ConnectionError)),
        reraise=True
    )
    def _do_search():
        api_url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={max_results}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"
        
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
        
    try:
        data = _do_search()
        results = []
        for item in data.get("items", []):
            results.append({
                "name": item.get("full_name"),
                "url": item.get("html_url"),
                "stars": item.get("stargazers_count"),
                "language": item.get("language"),
                "description": item.get("description"),
                "last_updated": item.get("updated_at")[:10]
            })
        return results
    except Exception as e:
        logger.error(f"GitHub API failed after retries: {e}")
        return [{"error": f"GitHub API failed: {str(e)}"}]


def github_readme_tool(owner_repo: str) -> Dict:
    """
    Fetches the README content for a given GitHub repository (e.g., 'owner/repo').
    """
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((HTTPError, Timeout, ConnectionError)),
        reraise=True
    )
    def _do_fetch():
        api_url = f"https://api.github.com/repos/{owner_repo}/readme"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"
        
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text

    try:
        content = _do_fetch()
        # Truncate to avoid token limits but keep enough for meaningful extraction
        return {"owner_repo": owner_repo, "readme": content[:2000]}
    except Exception as e:
        logger.error(f"GitHub README fetch failed for {owner_repo}: {e}")
        return {"error": f"Failed to fetch README for {owner_repo}: {str(e)}"}


github_tool_def = {
    "type": "function",
    "function": {
        "name": "github_search_tool",
        "description": "Searches GitHub for repositories matching the query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for GitHub repositories."},
                "max_results": {"type": "integer", "description": "Maximum number of results to return.", "default": 5},
            },
            "required": ["query"],
        },
    },
}

github_readme_tool_def = {
    "type": "function",
    "function": {
        "name": "github_readme_tool",
        "description": "Fetches the README content for a specific GitHub repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "owner_repo": {"type": "string", "description": "The 'owner/repo' format string (e.g., 'facebook/react')."},
            },
            "required": ["owner_repo"],
        },
    },
}

# Tool mapping
tool_mapping = {
    "tavily_search_tool": tavily_search_tool,
    "github_search_tool": github_search_tool,
    "wikipedia_search_tool": wikipedia_search_tool,
    "arxiv_search_tool": arxiv_search_tool,
    "github_readme_tool": github_readme_tool,
}
