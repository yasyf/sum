import asyncio
import itertools
import os
import signal
import sys
import warnings
from pathlib import Path

import click
import langchain
from pydantic import BaseModel

from summ.classify import Classes, Classifier
from summ.cli.app import SummApp
from summ.pipeline import Pipeline
from summ.summ import Summ


class Options(BaseModel):
    debug: bool
    verbose: bool
    model_name: str


class CLI:
    """Provides a convient way to serve a Summ CLI."""

    @staticmethod
    def run(summ: Summ, pipe: Pipeline, is_demo: bool = False):
        """Starts the CLI.

        Args:
            summ: The Summ instance to use. You should pre-populate it with the path to your data.
            pipe: The Pipeline instance to use. You can a specify custom [Splitter][summ.splitter.Splitter] for different sources.

        Example:
            ```python
            from pathlib import Path

            from summ import Pipeline, Summ
            from summ.cli import CLI
            from summ.splitter.otter import OtterSplitter

            from my.classifiers import *

            if __name__ == "__main__":
                summ = Summ(index="rpa-user-interviews")

                path = Path(__file__).parent.parent / "interviews"
                pipe = Pipeline.default(path, summ.index)
                pipe.splitter = OtterSplitter(speakers_to_exclude=["markie"])

                CLI.run(summ, pipe)
            ```
        """

        def handler(signum, frame):
            print("Cleaning up...")
            with open(os.devnull, "w") as devnull:
                sys.stdout = sys.stderr = devnull
                if task := asyncio.current_task():
                    task.cancel()
                if loop := asyncio.get_event_loop():
                    loop.stop()
                    loop.close()
                os._exit(1)

        signal.signal(signal.SIGINT, handler)
        warnings.simplefilter("ignore", ResourceWarning)

        @click.group(invoke_without_command=True)
        @click.option("--debug/--no-debug", default=True)
        @click.option("--verbose/--no-verbose", default=False)
        @click.option("-n", default=3)
        @click.pass_context
        def cli(ctx, debug: bool, verbose: bool, n: int):
            ctx.obj = Options(debug=debug, verbose=verbose)
            langchain.verbose = verbose
            summ.n = n

            if not ctx.invoked_subcommand:
                SummApp(summ, pipe, is_demo=is_demo).run()

        @cli.command()
        @click.pass_context
        def populate(ctx: click.Context):
            summ.populate(
                Path(pipe.importer.dir), pipe=pipe, parallel=not ctx.obj.verbose
            )

        class_options = set(
            itertools.chain.from_iterable(
                [list(c.classes) for c in Classifier.classifiers.values()]
            )
        )

        if not class_options:
            click.secho("Warning: No classifiers detected.", fg="yellow")

        @cli.command()
        @click.argument("query", nargs=1)
        @click.option(
            "--classes",
            multiple=True,
            default=[],
            type=click.Choice(list(class_options), case_sensitive=False),
        )
        @click.pass_context
        def query(ctx: click.Context, query: str, classes: list[Classes]):
            response = summ.query(
                query,
                classes=classes,
                corpus=list(pipe.corpus()),
                debug=ctx.obj.debug,
            )
            click.echo("\n")
            click.secho(response)

        cli()
