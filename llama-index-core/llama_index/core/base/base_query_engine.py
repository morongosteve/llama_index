"""Base query engine."""

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from llama_index.core.base.response.schema import RESPONSE_TYPE
from llama_index.core.callbacks.base import CallbackManager
from llama_index.core.prompts.mixin import PromptDictType, PromptMixin
from llama_index.core.schema import NodeWithScore, QueryBundle, QueryType
from llama_index.core.instrumentation import DispatcherSpanMixin
from llama_index.core.instrumentation.events.query import (
    QueryEndEvent,
    QueryStartEvent,
)
import llama_index.core.instrumentation as instrument

dispatcher = instrument.get_dispatcher(__name__)
logger = logging.getLogger(__name__)


class BaseQueryEngine(PromptMixin, DispatcherSpanMixin):
    """Base class for all query engines.

    A query engine takes a natural language query and returns a structured
    ``RESPONSE_TYPE`` that contains both the synthesized answer and the
    source nodes used to produce it.

    Subclasses must implement ``_query`` and ``_aquery``.

    Args:
        callback_manager: Optional callback manager for tracing and event hooks.
    """

    def __init__(
        self,
        callback_manager: Optional[CallbackManager],
    ) -> None:
        self.callback_manager = callback_manager or CallbackManager([])

    def _get_prompts(self) -> Dict[str, Any]:
        """Get prompts."""
        return {}

    def _update_prompts(self, prompts: PromptDictType) -> None:
        """Update prompts."""

    @dispatcher.span
    def query(self, str_or_query_bundle: QueryType) -> RESPONSE_TYPE:
        """Run a query against the engine and return a response.

        Args:
            str_or_query_bundle: A plain query string or a ``QueryBundle``
                containing the query and optional embedding information.

        Returns:
            A ``RESPONSE_TYPE`` containing the synthesized answer and
            source nodes.
        """
        dispatcher.event(QueryStartEvent(query=str_or_query_bundle))
        with self.callback_manager.as_trace("query"):
            if isinstance(str_or_query_bundle, str):
                str_or_query_bundle = QueryBundle(str_or_query_bundle)
            query_result = self._query(str_or_query_bundle)
        dispatcher.event(
            QueryEndEvent(query=str_or_query_bundle, response=query_result)
        )
        return query_result

    @dispatcher.span
    async def aquery(self, str_or_query_bundle: QueryType) -> RESPONSE_TYPE:
        """Async version of ``query``.

        Args:
            str_or_query_bundle: A plain query string or a ``QueryBundle``.

        Returns:
            A ``RESPONSE_TYPE`` containing the synthesized answer and
            source nodes.
        """
        dispatcher.event(QueryStartEvent(query=str_or_query_bundle))
        with self.callback_manager.as_trace("query"):
            if isinstance(str_or_query_bundle, str):
                str_or_query_bundle = QueryBundle(str_or_query_bundle)
            query_result = await self._aquery(str_or_query_bundle)
        dispatcher.event(
            QueryEndEvent(query=str_or_query_bundle, response=query_result)
        )
        return query_result

    def retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        """Retrieve relevant nodes for a query without synthesizing a response.

        Not all query engines support this method. Use ``query`` directly
        if this raises ``NotImplementedError``.

        Args:
            query_bundle: The query to retrieve nodes for.

        Returns:
            List of scored nodes relevant to the query.

        Raises:
            NotImplementedError: If the engine does not support retrieval
                as a separate step.
        """
        raise NotImplementedError(
            "This query engine does not support retrieve, use query directly"
        )

    def synthesize(
        self,
        query_bundle: QueryBundle,
        nodes: List[NodeWithScore],
        additional_source_nodes: Optional[Sequence[NodeWithScore]] = None,
    ) -> RESPONSE_TYPE:
        """Synthesize a response from a query and pre-retrieved nodes.

        Not all query engines support this method. Use ``query`` directly
        if this raises ``NotImplementedError``.

        Args:
            query_bundle: The original query.
            nodes: Pre-retrieved nodes to synthesize from.
            additional_source_nodes: Extra source nodes to include in the
                response metadata.

        Returns:
            A ``RESPONSE_TYPE`` with the synthesized answer.

        Raises:
            NotImplementedError: If the engine does not support synthesis
                as a separate step.
        """
        raise NotImplementedError(
            "This query engine does not support synthesize, use query directly"
        )

    async def asynthesize(
        self,
        query_bundle: QueryBundle,
        nodes: List[NodeWithScore],
        additional_source_nodes: Optional[Sequence[NodeWithScore]] = None,
    ) -> RESPONSE_TYPE:
        """Async version of ``synthesize``.

        Args:
            query_bundle: The original query.
            nodes: Pre-retrieved nodes to synthesize from.
            additional_source_nodes: Extra source nodes to include in the
                response metadata.

        Returns:
            A ``RESPONSE_TYPE`` with the synthesized answer.

        Raises:
            NotImplementedError: If the engine does not support synthesis
                as a separate step.
        """
        raise NotImplementedError(
            "This query engine does not support asynthesize, use aquery directly"
        )

    @abstractmethod
    def _query(self, query_bundle: QueryBundle) -> RESPONSE_TYPE:
        """Execute the query logic. Subclasses must implement this.

        Args:
            query_bundle: The query to execute.

        Returns:
            A ``RESPONSE_TYPE`` with the answer and source nodes.
        """

    @abstractmethod
    async def _aquery(self, query_bundle: QueryBundle) -> RESPONSE_TYPE:
        """Async version of ``_query``. Subclasses must implement this.

        Args:
            query_bundle: The query to execute.

        Returns:
            A ``RESPONSE_TYPE`` with the answer and source nodes.
        """
