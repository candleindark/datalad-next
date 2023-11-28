""" Functions that allow to route data around upstream iterator """

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Generator,
    Iterable,
)


__all__ = ['dont_process', 'join_with_list', 'route_in', 'route_out']


dont_process = object()


def route_out(iterable: Iterable,
              data_store: list,
              splitter: Callable[[Any], tuple[Any, Any | None]],
              ) -> Generator:
    """ Route data around the consumer of this iterable

    :func:`route_out` allows its user to:

     1. store data that is received from an iterable,
     2. determine whether this data should be yielded to a consumer of
        ``route_out``, by calling :func:`splitter`.

    To determine which data is to be yielded to the consumer and which data
    should only be stored but not yielded, :func:`route_out` calls
    :func:`splitter`. :func:`splitter` is called for each element of the input
    iterable, with the element as sole argument. The function should return a
    tuple of two elements. The first element is the data that is to be
    yielded to the consumer. The second element is the data that is to be
    stored in the list ``data_store``. If the first element of the tuple is
    ``datalad_next.itertools.dont_process``, no data is yielded to the
    consumer.

    :func:`route_in` can be used to combine data that was previously
    stored by :func:`route_out` with the data that is yielded by
    :func:`route_out` and with the data the was not processed, i.e. not yielded
    by :func:`route_out`.

    The elements yielded by :func:`route_in` will be in the same
    order in which they were passed into :func:`route_out`, including the
    elements that were not yielded by :func:`route_out` because :func:`splitter`
    returned ``dont_process`` in the first element of the result-tuple.

    The combination of the two functions :func:`route_out` and :func:`route_in`
    can be used to "carry" additional data along with data that is processed by
    iterators. And it can be used to route data around iterators that cannot
    process certain data.

    For example, a user has an iterator to divide all number in a list by the
    number ``2``. The user wants the iterator to process all numbers in a list,
    except from zeros, In this case :func:`route_out` and :func:`route_in` can
    be used as follows:

    .. code-block:: python

        from math import nan
        from datalad_next.itertools import route_out, route_in, dont_process

        def splitter(data):
            # if data == 0, return `dont_process` in the first element of the
            # result tuple to indicate that route_out should not yield this
            # element to its consumer
            return (dont_process, [data]) if data == 0 else (data, [data])

        def joiner(processed_data, stored_data):
            #
            return nan if processed_data is dont_process else processed_data

        numbers = [0, 1, 0, 2, 0, 3, 0, 4]
        store = list()
        r = route_in(
            map(
                lambda x: x / 2.0,
                route_out(
                    numbers,
                    store,
                    splitter
                )
            ),
            store,
            joiner
        )
        print(list(r))

    The example about will print ``[nan, 0.5, nan, 1.0, nan, 1.5, nan, 2.0]``.

    Parameters
    ----------
    iterable: Iterable
        The iterable that yields the input data
    data_store: list
        The list that is used to store the data that is routed out
    splitter: Callable[[Any], tuple[Any, Any | None]]
        The function that is used to determine which part of the input data,
        if any, is to be yielded to the consumer and which data is to
        be stored in the list ``data_store``. The function is called with each
        The function is called for each element of
        the input iterable with the element as sole argument. It should return a
        tuple of two elements. If the first element is not
        ``datalad_next.itertools.dont_process``, it is yielded to the consumer.
        If the first element is ``datalad_next.itertools.dont_process``,
        nothing is yielded to the consumer. The second element is stored in the
        list ``data_store``.
        The cardinality of ``data_store`` will be the same as the cardinality of
        the input iterable.
    """
    for item in iterable:
        data_to_process, data_to_store = splitter(item)
        if data_to_process is dont_process:
            data_store.append((False, data_to_store))
        else:
            data_store.append((True, data_to_store))
            yield data_to_process

def route_in(iterable: Iterable,
             data_store: list,
             joiner: Callable[[Any, Any], Any]
             ) -> Generator:
    """ Yield previously rerouted data to the consumer

    This function is the counter-part to :func:`route_out`. It takes the iterable
    ``iterable`` and a data store given in ``data_store`` and yields elements
    in the same order in which :func:`route_out` received them from its
    underlying iterable (using the same data store). This includes elements that
    were not yielded by :func:`route_out`, but only stored.

    :func:`route_in` uses  :func:`joiner`-function to determine how stored and
    optionally processed data should be joined into a single element, which is
    then yielded by :func:`route_in`.
    :func:`route_in` calls :func:`joiner` with a 2-tuple. The first
    element of the tuple is either ``dont_process`` or the next item from the
    underlying iterator. The second element is the data
    that was stored in the data store. :func:`joiner` should return a single
    element, which will be yielded by :func:`route_in`.

    This module provides a standard joiner-function: :func:`join_with_list`
    that works with splitter-functions that return a list as second element of
    the result tuple.

    The cardinality of ``iterable`` must match the number of processed data
    elements in the data store. The output cardinality of :func:`route_in` will
    be the cardinality of the input iterable of the corresponding
    :func:`route_out`-call. Given the following code:

    .. code-block:: python

        store_1 = list()
        route_in(
            some_generator(
                route_out(input_iterable, store_1, splitter_1)
            ),
            store_1,
            joiner_1
        )

    :func:`route_in` will yield the same number of elements as ``input_iterable``.
    But, the number of elements processed by ``some_generator`` is determined by
    the :func:`splitter_1` in :func:`route_out`, i.e. by the number of
    :func:`splitter_1`-results that have don't have
    ``datalad_next.itertools.don_process`` as first element.

    Parameters
    ----------
    iterable: Iterable
        The iterable that yields the input data.
    data_store: list
        The list from which the data that be routed is read.
    joiner: Callable[[Any, Any], Any]
        A function that determines how the data that is yielded by
        ``iterable`` should be combined with the corresponding data from
        ``data_store``, in order to yield the final result.
        The first argument to ``joiner`` is the data that is yielded by
        ``iterable``, or ``datalad_next.itertools.dont_process`` if no data
        was processed in the corresponding step. The second argument is the
        data that was stored in ``data_store`` in the corresponding step.
    """
    for element in iterable:
        process_info = data_store.pop(0)
        while not process_info[0]:
            yield joiner(dont_process, process_info[1])
            process_info = data_store.pop(0)
        yield joiner(element, process_info[1])
    for process_info in data_store:
        assert process_info[0] is False
        yield joiner(dont_process, process_info[1])
    del data_store[:]


def join_with_list(processed_data: Any,
                   stored_data: list
                   ) -> list:
    """ A standard joiner that works with splitter-functions that store a list

        This joiner is used in combination with splitters that return a list as
        second element of the result tuple, i.e. splitters that will store a
        list in their data store.

        :func:`join_with_list` adds ``processed_data`` as first element to the
        list ``stored_data``. The extended list is then yielded by
        :func:`route_in`.

        Parameters
        ----------
        processed_data: Any
            The data that was yielded by the underlying iterable of the
            :func:`route_in`-call, if data was processed. If no data was
            processed: ``datalad_next.itertools.dont_process``.
        stored_data: list
            The data that was stored in the data store provided at the
            :func:`route_in`-call.

        Returns
        -------
        list
            If ``processed_data is datalad_next.itertools.dont_process``, the
            result will be ``[None] + stored_data``. If ``processed_data`` is
            any other object, the result will be equivalent to
            ``[processed_data] + stored_data``.
    """
    if processed_data is dont_process:
        return [None] + stored_data
    if not isinstance(processed_data, list):
        return [processed_data] + stored_data
    processed_data.extend(stored_data)
    return processed_data
