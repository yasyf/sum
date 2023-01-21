import re
from dataclasses import dataclass
from textwrap import dedent

from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain.docstore.document import Document
from langchain.llms import OpenAI

from user_interview_summary.classify.classes import Classes
from user_interview_summary.shared.chain import Chain


@dataclass
class Source:
    file: str
    classes: list[Classes]
    chunk: str


@dataclass
class Fact:
    fact: str
    source: str


class Factifier(Chain):
    PROMPT_TEMPLATE = PromptTemplate(
        template=dedent(
            """
            Your task is to take a paragraph, and extract any pertinent facts from it.
            The facts should be formatted in a bulleted list.

            Paragraph:
            {chunk}

            Facts:
            -
            """
        ),
        input_variables=["chunk"],
    )

    def _parse(self, results: list[str]):
        return [
            p.group("fact")
            for r in results
            for p in [re.search(r"-(?:\s*)(?P<fact>.*)", r)]
            if p
        ]

    def factify(self, doc: Document) -> list[str]:
        chain = LLMChain(llm=self.llm, prompt=self.PROMPT_TEMPLATE)
        results = chain.run(doc.page_content)
        return self._parse(results.splitlines())
