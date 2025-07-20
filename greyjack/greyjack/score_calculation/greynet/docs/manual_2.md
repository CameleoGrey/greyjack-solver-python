Of course. Here is a comprehensive reference guide to the Greynet engine, structured in a top-down manner.

***

# Greynet Reference Manual

Welcome to the official reference manual for Greynet, a high-performance, forward-chaining rules engine for Python. This document provides a top-down exploration of the engine, from high-level concepts to the intricacies of its internal architecture.

## Table of Contents

1. **Introduction to Greynet**
   * What is Greynet?
   * Core Concepts
   * A First Example: "Hello, Greynet"
2. **The Constraint Lifecycle**
   * `ConstraintBuilder`: The Rule Architect
   * `Session`: The Runtime Engine
   * Scoring and Weights
3. **The Stream API: Defining Logic**
   * Starting a Stream
   * Filtering & Transformation
   * Joining Streams
   * Aggregation with `group_by`
   * Conditional Logic
4. **Advanced Stream Operations**
   * Temporal Windowing
   * Sequential Pattern Matching
5. **The Collector Toolkit**
   * Basic Aggregators
   * Compositional Collectors
   * Specialized Collectors
6. **Under the Hood: The Rete Network**
   * Core Principles
   * Anatomy of the Network (Node Types)
   * Data Flow and Memory Management

---

## 1. Introduction to Greynet

This section covers the fundamental principles of Greynet, its core components, and a simple example to get you started.

### What is Greynet?

Greynet is a declarative rules engine designed for solving complex event processing and constraint satisfaction problems. It is built upon the principles of the **Rete algorithm**, which provides a highly efficient method for matching a large collection of facts against a large collection of rules.

Its key features include:

* **Declarative, Fluent API**: Define complex rules through a clean, chainable `Stream` API.
* **High Performance**: Utilizes the Rete algorithm, node sharing, and object pooling to minimize redundant calculations and memory overhead.
* **Dynamic Configuration**: Constraint penalties can be updated at runtime, allowing for immediate re-evaluation of the problem space without rebuilding the engine.
* **Rich Functionality**: Natively supports complex joins, aggregations, conditional logic (`exists`/`not exists`), and advanced temporal/sequential pattern matching.

### Core Concepts

Understanding these four concepts is key to using Greynet effectively.

* #### **Fact**
  
  A Fact is any plain Python object (often a `dataclass`) that represents a piece of data in the system. Facts are the "what" that your rules operate on. For example, a `RoomBooking` or a `UserLoginEvent`.

* #### **Stream**
  
  A Stream is a fluent, declarative API for defining the logic of a single rule. You start a stream from a collection of facts and apply a series of operations like `filter()`, `join()`, and `group_by()` to define the conditions for a constraint violation.

* #### **Constraint**
  
  A Constraint is a specific rule that, when its conditions are met, applies a penalty to the overall score. It is the terminal operation of a Stream, defined by methods like `penalize_hard()`.

* #### **Session**
  
  The Session is the runtime environment for the Greynet engine. It holds all the facts, manages the Rete network, and calculates the total score. You interact with the session by inserting, retracting, and updating facts.

### A First Example: "Hello, Greynet"

Let's model a simple scheduling rule: **Two meetings cannot overlap in the same room.**

* #### **Step 1: Define the Fact**
  
  We need a way to represent a meeting. A `dataclass` is perfect for this.
  
  ```python
  from dataclasses import dataclass
  from datetime import datetime
  
  @greynet_fact
@dataclass()
  class Meeting:
      id: str
      room: str
      start_time: datetime
      end_time: datetime
  ```

* #### **Step 2: Define the Constraint**
  
  We use `ConstraintBuilder` to define our rule set. The rule logic is defined using the Stream API.
  
  ```python
  from greynet import ConstraintBuilder, JoinerType
  
  # Initialize the builder
  builder = ConstraintBuilder(name="scheduling_rules")
  
  # The @constraint decorator registers the rule
  @builder.constraint("Overlapping Meetings")
  def overlapping_meetings():
      # Start two streams from the Meeting fact
      meetings1 = builder.for_each(Meeting)
      meetings2 = builder.for_each(Meeting)
  
      return (
          # 1. Join meetings with themselves if they are in the same room
          meetings1.join(meetings2,
              JoinerType.EQUAL,
              lambda m: m.room, # Left key
              lambda m: m.room  # Right key
          )
          # 2. Ensure we don't match a meeting with itself or get duplicates (m1, m2) and (m2, m1)
          .filter(lambda m1, m2: m1.id < m2.id)
          # 3. Filter for pairs that actually overlap in time
          .filter(lambda m1, m2: max(m1.start_time, m2.start_time) < min(m1.end_time, m2.end_time))
          # 4. If all conditions are met, apply a penalty
          .penalize_hard(1)
      )
  ```

* #### **Step 3: Build the Session and Interact**
  
  Once the rules are defined, we build the session and can start inserting facts.
  
  ```python
  from datetime import datetime, timedelta
  
  # Build the session from the defined constraints
  session = builder.build()
  
  # Define some meetings
  m1 = Meeting("m1", "Room A", datetime(2025, 7, 16, 9), datetime(2025, 7, 16, 10))
  m2 = Meeting("m2", "Room B", datetime(2025, 7, 16, 9), datetime(2025, 7, 16, 10))
  m3 = Meeting("m3", "Room A", datetime(2025, 7, 16, 9, 30), datetime(2025, 7, 16, 10, 30)) # Overlaps with m1
  
  # Insert facts into the session
  session.insert_batch([m1, m2, m3])
  
  # Get the total score. The score object shows the penalty from the violation.
  score = session.get_score()
  print(f"Total Score: {score}") # Output: Total Score: <SimpleScore simple_value=1>
  
  # Get a detailed breakdown of which facts violated the constraint
  matches = session.get_constraint_matches()
  print(f"Violations: {matches}")
  # Output: Violations: {'Overlapping Meetings': [(<SimpleScore simple_value=1>, <BiTuple fact_a=...m1, fact_b=...m3>)]}
  ```

This example demonstrates the core workflow: define facts, build rules with a fluent API, create a session, and use it to evaluate your data.

---

## 2. The Constraint Lifecycle

This section covers the main components responsible for defining, building, and executing constraints.

### `ConstraintBuilder`: The Rule Architect

The `ConstraintBuilder` is the factory for creating a `Session`. It collects all your rule definitions before compiling them into an efficient Rete network.

#### Key Methods

* #### `ConstraintBuilder(name, score_class=SimpleScore, weights=None)`
  
  * `name`: A descriptive name for the rule package.
  * `score_class`: The class used to represent the score (e.g., `SimpleScore`, `HardSoftScore`). It must have a static `get_score_fields()` method.
  * `weights`: An optional `ConstraintWeights` object to enable dynamic, runtime updates to penalties.

* #### `@builder.constraint(constraint_id, default_weight=1.0)`
  
  This decorator registers a function as a constraint definition.
  
  * `constraint_id`: A unique string identifier for the rule.
  * `default_weight`: A default multiplier for the penalty.
    The decorated function must return a `Constraint` object, which is created by calling a `.penalize_*()` method on a stream.

* #### `builder.for_each(fact_class)`
  
  This is the entry point for every rule. It creates a `Stream` that will emit any facts of the given `fact_class` that are inserted into the session.

* #### `builder.build(**kwargs)`
  
  This method compiles all the registered constraints into a `Session`. It builds the Rete network, sets up node sharing, and prepares the session for execution.

### `Session`: The Runtime Engine

The `Session` is your primary interface for interacting with the rules engine at runtime.

#### Key Methods

* #### `insert(fact)` / `insert_batch(facts)`
  
  Adds one or more facts to the session's working memory, triggering the rule evaluation process.

* #### `retract(fact)` / `retract_batch(facts)`
  
  Removes one or more facts from working memory, reversing any consequences of their previous insertion.

* #### `flush()`
  
  Greynet uses a scheduler to batch changes for efficiency. `flush()` forces the immediate processing of all pending insertions and retractions. Methods like `get_score()` and `get_constraint_matches()` call `flush()` implicitly.

* #### `get_score()`
  
  Calculates and returns the total aggregated score from all constraint violations. The type of the returned object is determined by the `score_class` set in the `ConstraintBuilder`.

* #### `get_constraint_matches()`
  
  Returns a dictionary detailing every constraint violation. The keys are the `constraint_id`s, and the values are lists of tuples, where each tuple contains the score object and the fact(s) that caused the violation.

* #### `update_constraint_weight(constraint_id, new_weight)`
  
  If the session was built with a `ConstraintWeights` object, this method allows you to change the penalty multiplier for a specific constraint at runtime. The engine will automatically and efficiently recalculate the scores for all existing matches of that constraint.

* #### `clear()`
  
  Retracts all known facts from the session, effectively resetting it to an empty state.

### Scoring and Weights

The final step of any rule definition is to specify *how* a violation should be scored.

* #### Penalty Methods
  
  Every `Stream` has penalty methods that terminate the stream and create a `Constraint` object.
  
  * `penalize_hard(...)`
  * `penalize_medium(...)`
  * `penalize_soft(...)`
  * `penalize_simple(...)`
    The names correspond to different fields in a score object (e.g., `HardSoftScore`), allowing you to categorize penalties. The `penalize_simple` method targets the `simple_value` field in the default `SimpleScore`.

* #### Dynamic Penalties
  
  The argument to a penalty method can be a static number or a callable `lambda` function. If it's a lambda, it will be executed with the matching facts as arguments, allowing you to calculate a penalty based on the data itself.
  
  ```python
  # Example: Penalty scales with the duration of the overlap
  from datetime import timedelta
  
  .penalize_soft(lambda m1, m2: (min(m1.end_time, m2.end_time) - max(m1.start_time, m2.start_time)).total_seconds())
  ```

* #### `ConstraintWeights`
  
  This thread-safe class manages the weight multipliers for each constraint. When you call `update_constraint_weight` on the session, you are modifying a shared `ConstraintWeights` object. The final penalty for any violation is calculated as:
  $$ \text{final\_penalty} = \text{base\_penalty\_value} \times \text{dynamic\_weight} $$

This concludes the high-level overview of defining and running constraints. The next section will dive deep into the Stream API, which forms the core of the rule definition logic.

---

*(This response is the first part of a multi-part guide. Subsequent parts will cover the Stream API, advanced features, and internal architecture in detail.)*

Of course. Here is the next part of the Greynet Reference Manual, focusing on the powerful Stream API.

***

## 3. The Stream API: Defining Logic

The Stream API is the heart of Greynet's declarative rule engine. It provides a fluent, chainable interface to express complex logic, starting from raw facts and progressively filtering, transforming, joining, and aggregating them until a specific condition for a constraint violation is met.

Each operation in the chain creates a new `Stream` object, representing a new state in the data processing pipeline. Under the hood, Greynet translates this chain of streams into an efficient network of nodes.

### Visualizing a Stream

A simple stream can be visualized as a data flow pipeline:

```mermaid
graph TD
    A[for_each(Meeting)] --> B(filter);
    B --> C(penalize_hard);
    subgraph Stream Definition
        direction LR
        A
        B
        C
    end
```

### Starting a Stream

All rule logic begins by creating a stream from a source of facts.

* #### `builder.for_each(FactClass)`
  
  This method creates the initial `Stream`. It will be populated with every object of `FactClass` that is inserted into the session. The stream's elements are `UniTuple` objects, each containing a single fact.
  
  ```python
  # Creates a stream of UniTuple<Meeting>
  meetings_stream = builder.for_each(Meeting)
  ```

### Filtering & Transformation

These operations modify the elements within a single stream.

* #### `stream.filter(predicate)`
  
  The most common operation. It filters the stream, only allowing tuples that satisfy the `predicate` to pass through. The `predicate` is a `lambda` function that receives the contents of the tuple as arguments.
  
  ```python
  # Before filter: Stream of all meetings
  # After filter: Stream of meetings in Room A only
  meetings_in_room_a = builder.for_each(Meeting).filter(lambda m: m.room == "Room A")
  ```

* #### `stream.map(mapper)`
  
  Transforms each element in the stream into a *single new element*. The result is a new `Stream` of `UniTuple` objects containing the mapped elements.
  
  ```python
  # Before map: Stream of Meeting objects
  # After map: Stream of strings (room names)
  room_names = builder.for_each(Meeting).map(lambda m: m.room)
  ```

* #### `stream.flat_map(mapper)`
  
  A more powerful version of `map`. It transforms each element into an *iterable* of new elements. The engine then flattens all the generated iterables into a single output stream.
  
  ```python
  @dataclass
  class Team:
      name: str
      members: list[str]
  
  # Before flat_map: Stream of Team objects
  # After flat_map: Stream of strings (individual member names)
  all_members = builder.for_each(Team).flat_map(lambda t: t.members)
  ```

### Joining Streams

Joins are fundamental to finding relationships between different facts. Greynet supports a variety of join types.

* #### `stream.join(other_stream, joiner_type, left_key_func, right_key_func)`
  
  Combines two streams into one. A new combined tuple is created for each pair of tuples (one from the left stream, one from the right) that satisfies the join condition.
  
  * `other_stream`: The stream to join with.
  * `joiner_type`: An enum from `greynet.common.joiner_type.JoinerType`.
  * `left_key_func` / `right_key_func`: Lambda functions that extract the join key from a tuple in the left/right stream, respectively.
  
  The arity of the resulting stream is the sum of the arities of the input streams. For example, joining two `UniTuple` streams results in a `BiTuple` stream.
  
  #### Common `JoinerType` values:
  
  * `EQUAL`: The default and most common join type.
  * `NOT_EQUAL`
  * `LESS_THAN`, `GREATER_THAN`, etc.
  * `RANGE_OVERLAPS`: For joining on time intervals or numeric ranges.
  
  ```python
  @greynet_fact
@dataclass()
  class Room:
      name: str
      capacity: int
  
  # Join Meetings with Rooms to find over-capacity meetings
  overbooked = (
      builder.for_each(Meeting)
      .join(builder.for_each(Room),
            JoinerType.EQUAL,
            lambda m: m.room,      # Key from Meeting stream
            lambda r: r.name       # Key from Room stream
      )
      # The resulting stream contains BiTuple(meeting, room)
      .filter(lambda meeting, room: meeting.attendee_count > room.capacity)
      .penalize_hard(1)
  )
  ```

### Aggregation with `group_by`

`group_by` is used to aggregate facts that share a common key. This is the foundation for rules like "a user cannot have more than 3 active sessions" or "calculate the average transaction value per customer."

* #### `stream.group_by(group_key_function, collector_supplier)`
  
  This operation collapses a stream into a new `Stream` of `BiTuple` objects.
  
  * `group_key_function`: A lambda that extracts the grouping key from each fact.
  * `collector_supplier`: A function that supplies a **Collector** instance. The collector defines *how* the facts within each group are aggregated.
  
  The output stream contains `BiTuple`s where:
  
  * `fact_a` is the group key.
  * `fact_b` is the result of the aggregation from the collector.
  
  ```python
  from greynet import Collectors
  
  # Rule: Any user with more than 3 logins is flagged.
  too_many_logins = (
      builder.for_each(UserLoginEvent)
      .group_by(
          lambda event: event.user_id,    # Group by the user's ID
          Collectors.count()              # The aggregation is a simple count
      )
      # The stream now contains BiTuple(user_id, count)
      .filter(lambda user_id, count: count > 3)
      .penalize_soft(1)
  )
  ```
  
  The `Collectors` class provides a rich toolkit for various aggregations, covered in Section 5.

### Conditional Logic (`exists` / `not exists`)

These powerful operations allow you to express rules that depend on the presence or absence of other facts, without needing to perform a full join.

* #### `stream.if_exists(other_stream, left_key, right_key)`
  
  Propagates a tuple from the original stream **only if** at least one matching fact exists in `other_stream` based on the provided keys. The output stream has the same arity and content as the original stream.

* #### `stream.if_not_exists(other_stream, left_key, right_key)`
  
  The inverse of `if_exists`. Propagates a tuple **only if** no matching facts exist in `other_stream`.
  
  ```python
  @greynet_fact
@dataclass()
  class Order:
      id: str
      customer_id: str
  
  @greynet_fact
@dataclass()
  class Payment:
      order_id: str
      customer_id: str
  
  # Find all orders that do NOT have a corresponding payment.
  unpaid_orders = (
      builder.for_each(Order)
      .if_not_exists(
          builder.for_each(Payment),
          left_key=lambda order: order.id,    # Key from Order stream
          right_key=lambda pmt: pmt.order_id # Key from Payment stream
      )
      .penalize_medium(1)
  )
  ```

This concludes the core Stream API. The next section will explore the advanced operations for handling temporal and sequential data.

---

*(This response is the second part of a multi-part guide. Subsequent parts will cover advanced streams, collectors, and the internal architecture.)*

Of course. Here is the third part of the Greynet Reference Manual, detailing the advanced stream operations for temporal and sequential analysis.

***

## 4. Advanced Stream Operations

While the core API covers a vast range of use cases, modern systems often require analysis based on time and the order of events. Greynet provides powerful, dedicated stream operations for these scenarios. These operations can only be applied to a `Stream` of `UniTuple` (a stream of single facts).

### Temporal Windowing

Windowing is the process of grouping facts into time-based buckets. This is essential for time-series analysis, such as calculating moving averages or detecting spikes in activity.

The windowing process starts with the `.window()` method, which requires a `time_extractor` function to tell the engine how to get a `datetime` object from your fact. This method returns a special `WindowedStream` object, which then allows you to specify the type of window.

* #### `stream.window(time_extractor).sliding(size, slide)`
  
  Creates overlapping windows.
  
  * `size`: A `timedelta` defining the total duration of each window.
  * `slide`: A `timedelta` defining how far the window moves forward for each step. For a sliding window, `slide` must be less than `size`.
  
  The output is a `Stream` of `BiTuple`s, where for each window:
  
  * `fact_a` is the `datetime` object representing the window's start time.
  * `fact_b` is a `list` of all facts that fall within that window.
  
  ##### Example: Detect more than 10 API calls from a single IP in any 1-minute interval.
  
  ```python
  from greynet import Collectors
  from datetime import timedelta
  
  @greynet_fact
@dataclass()
  class ApiCall:
      ip_address: str
      timestamp: datetime
  
  # The rule definition
  too_many_requests = (
      builder.for_each(ApiCall)
      # First, group calls by IP address
      .group_by(
          lambda call: call.ip_address,
          Collectors.to_list() # Collect all calls for each IP
      )
      # The stream is now BiTuple(ip_address, [list_of_calls])
      # Flatten the list of calls into a stream of individual calls for windowing
      .flat_map(lambda ip, calls: calls)
      # Now, apply a sliding window to the stream of individual calls
      .window(time_extractor=lambda call: call.timestamp)
      .sliding(size=timedelta(minutes=1), slide=timedelta(seconds=10))
      # The stream is now BiTuple(window_start_time, [calls_in_window])
      # We only care about windows with more than 10 calls
      .filter(lambda window_start, calls: len(calls) > 10)
      .penalize_soft(1)
  )
  ```

* #### `stream.window(time_extractor).tumbling(size)`
  
  Creates fixed, non-overlapping windows. Each fact belongs to exactly one window. This is equivalent to a sliding window where `slide == size`.
  
  * `size`: A `timedelta` defining the duration of each window.
  
  The output format is identical to that of a sliding window.
  
  ##### Example: Calculate the total value of transactions per hour.
  
  ```python
  # Fact definition
  @greynet_fact
@dataclass()
  class Transaction:
      id: str
      amount: float
      timestamp: datetime
  
  # Rule Definition
  hourly_transaction_value = (
      builder.for_each(Transaction)
      .window(time_extractor=lambda tx: tx.timestamp)
      .tumbling(size=timedelta(hours=1))
      # Stream is BiTuple(hour_start_time, [transactions_in_hour])
      # Now we can map this to calculate the sum
      .map(lambda hour_start, transactions: (hour_start, sum(tx.amount for tx in transactions)))
      # This stream can now be used for other rules, e.g., flagging hours with unusually high volume.
  )
  ```

### Sequential Pattern Matching

Sometimes, the specific *order* of events is more important than their aggregate count. The `.sequence()` method is designed to detect complex patterns of events occurring in a specific chronological order within a given time frame.

* #### `stream.sequence(time_extractor, *steps, within, allow_gaps=True)`
  
  Finds sequences of facts that match an ordered series of conditions.
  
  * `time_extractor`: A function to get a `datetime` from the fact.
  * `*steps`: A variable number of predicate functions. Each function defines a condition for one step in the sequence.
  * `within`: A `timedelta` specifying the maximum allowed duration between the timestamp of the *first* fact in the sequence and the *last* fact.
  * `allow_gaps`: If `True` (default), other events that don't match the pattern can occur between the steps. If `False`, the sequence must be composed of consecutive matching events.
  
  The output is a `Stream` of `UniTuple`s. For each complete sequence found, the tuple's single fact is a `list` containing the facts that formed the sequence, in chronological order.
  
  ##### Example: Detect suspicious behavior (a user logs in, a critical action fails, and they immediately log out).
  
  ```python
  # Fact definitions
  @greynet_fact
@dataclass() class Login: user: str; timestamp: datetime
  @greynet_fact
@dataclass() class ActionFailed: user: str; action: str; timestamp: datetime
  @greynet_fact
@dataclass() class Logout: user: str; timestamp: datetime
  
  # A helper stream to unify all event types
  all_events = builder.for_each(object) # Matches any fact
  
  # The sequence rule
  suspicious_sequence = (
      all_events
      .sequence(
          # 1. Time Extractor
          time_extractor=lambda e: e.timestamp,
          # 2. Steps
          lambda e: isinstance(e, Login),
          lambda e: isinstance(e, ActionFailed) and e.action == "update_credentials",
          lambda e: isinstance(e, Logout),
          # 3. Time Window
          within=timedelta(minutes=2)
      )
      # Stream contains UniTuple([login_event, failed_event, logout_event])
      # Filter for sequences where all events are for the same user
      .filter(lambda event_list: len(set(e.user for e in event_list)) == 1)
      .penalize_hard(10)
  )
  ```

These advanced features enable Greynet to solve a class of problems that are difficult or impossible to express with simple joins and filters, making it a versatile tool for real-time monitoring and complex event processing.

---

*(This response is the third part of a multi-part guide. The next part will cover the rich Collector Toolkit used with `group_by`.)*

Of course. Here is the next part of the Greynet Reference Manual, focusing on the versatile Collector Toolkit.

***

## 5. The Collector Toolkit

When you use the `group_by` operation, you need to specify *how* the facts within each group should be aggregated. This is the job of a **Collector**. Greynet provides a rich set of pre-built collectors, accessible through the `greynet.Collectors` helper class.

Collectors are supplied as functions to `group_by` (e.g., `Collectors.count()`, not `Collectors.count`). This is because the engine needs to create a new instance of the collector for each group that is formed.

### Basic Aggregators

These are the most frequently used collectors for common aggregation tasks.

* #### `Collectors.count()`
  
  Simply counts the number of items in the group. The result is an integer.
  
  ```python
  # Count the number of tasks per project
  tasks_per_project = builder.for_each(Task).group_by(
      lambda task: task.project_id,
      Collectors.count()
  )
  # Resulting stream: BiTuple(project_id, count_of_tasks)
  ```

* #### `Collectors.sum(mapping_function)`
  
  Calculates the sum of the values extracted by the `mapping_function`. The result is a number.
  
  ```python
  # Calculate the total sales amount per region
  sales_per_region = builder.for_each(Sale).group_by(
      lambda sale: sale.region,
      Collectors.sum(lambda sale: sale.amount)
  )
  # Resulting stream: BiTuple(region, total_sales_amount)
  ```

* #### `Collectors.avg(mapping_function)`
  
  Calculates the average of the values extracted by the `mapping_function`. The result is a float.

* #### `Collectors.min(mapping_function)` / `Collectors.max(mapping_function)`
  
  Finds the minimum or maximum of the values extracted by the `mapping_function`.

* #### `Collectors.to_list()`
  
  Collects all items in the group into a `list`.

* #### `Collectors.to_set()`
  
  Collects all unique items in the group into a `set`.

* #### `Collectors.distinct()`
  
  Collects all unique items in the group into a `list`, preserving the order of insertion.

### Compositional Collectors

Sometimes you need to perform multiple aggregations on the same group. Instead of creating multiple `group_by` streams, you can use `compose` to do it all in one efficient pass.

* #### `Collectors.compose(collector_suppliers_dict)`
  
  Takes a dictionary where keys are descriptive names and values are other collector suppliers. The result of the aggregation is a dictionary containing the results of each sub-collector.
  
  ##### Example: For each project, get the task count, total budget, and a list of unique assignees.
  
  ```python
  project_summary = builder.for_each(Task).group_by(
      lambda task: task.project_id,
      Collectors.compose({
          'task_count': Collectors.count(),
          'total_budget': Collectors.sum(lambda t: t.cost),
          'assignees': Collectors.distinct(lambda t: t.assignee)
      })
  )
  # Resulting stream: BiTuple(project_id, summary_dict)
  # e.g., ('P-101', {'task_count': 5, 'total_budget': 15000, 'assignees': ['Alice', 'Bob']})
  
  # You can then filter based on the composed result
  high_cost_projects = project_summary.filter(
      lambda proj_id, summary: summary['total_budget'] > 50000
  )
  ```

### Specialized Collectors

These collectors provide more advanced or targeted functionality.

* #### `Collectors.filtering(predicate, downstream_supplier)`
  
  Filters items *within* a group before passing them to a downstream collector.
  
  ##### Example: Count only the 'High Priority' tasks within each project.
  
  ```python
  urgent_task_count = builder.for_each(Task).group_by(
      lambda task: task.project_id,
      Collectors.filtering(
          lambda task: task.priority == "High", # The filter to apply
          Collectors.count()                    # The collector for items that pass
      )
  )
  # Resulting stream: BiTuple(project_id, count_of_high_priority_tasks)
  ```

* #### `Collectors.mapping(mapping_function, downstream_supplier)`
  
  Applies a transformation to items *within* a group before passing them to a downstream collector.
  
  ##### Example: Calculate the average length of task descriptions per project.
  
  ```python
  avg_desc_length = builder.for_each(Task).group_by(
      lambda task: task.project_id,
      Collectors.mapping(
          lambda task: len(task.description), # The mapping to apply
          Collectors.avg(lambda length: length) # The collector for the mapped values
      )
  )
  ```

### Advanced Data Structure Collectors

These collectors aggregate items into sophisticated data structures for specialized use cases.

* #### `Collectors.to_bloom_filter(estimated_items, false_positive_rate)`
  
  Aggregates items into a `CountingBloomFilter`, a probabilistic data structure that is highly memory-efficient for checking set membership. It's useful when groups are very large and you only need to ask "is this item *probably* in the group?".

* #### `Collectors.consecutive_sequences(sequence_func)`
  
  Tracks and identifies runs of consecutive items. It's perfect for finding things like consecutive login days, unbroken streaks, or adjacent seat bookings.
  
  * `sequence_func`: A function that extracts a value (like a number or date) from the fact to check for consecutiveness.
  
  ##### Example: Find groups of consecutively numbered tickets.
  
  ```python
  # Fact: Ticket(id=1), Ticket(id=2), Ticket(id=4), Ticket(id=5)
  consecutive_tickets = builder.for_each(Ticket).group_by(
      lambda t: "all_tickets", # Group all tickets together
      Collectors.consecutive_sequences(lambda ticket: ticket.id)
  )
  # Result: [ConsecutiveSequence(start=1, end=2, ...), ConsecutiveSequence(start=4, end=5, ...)]
  ```

* #### `Collectors.connected_ranges(start_func, end_func)`
  
  Takes items that represent a range (e.g., a time interval) and merges any ranges that overlap or are immediately adjacent.
  
  * `start_func` / `end_func`: Functions to extract the start and end of the range from a fact.
  
  ##### Example: Find the actual busy time slots for a meeting room.
  
  ```python
  # Facts: Booking(start=9, end=10), Booking(start=9:30, end=10:30)
  busy_slots = builder.for_each(Booking).group_by(
      lambda b: b.room_id,
      Collectors.connected_ranges(
          start_func=lambda b: b.start_time,
          end_func=lambda b: b.end_time
      )
  )
  # Result: [ConnectedRange(start=9, end=10:30, ...)]
  ```

This comprehensive toolkit allows `group_by` to be one of the most powerful and flexible operations in Greynet, enabling a wide array of stateful aggregations.

---

*(This response is the fourth part of a multi-part guide. The final part will provide a glimpse into the engine's internal Rete network architecture.)*

Of course. Here is the final part of the Greynet Reference Manual, which delves into the engine's internal architecture.

***

## 6. Under the Hood: The Rete Network

The declarative Stream API provides a simple and powerful way to define rules. This simplicity is made possible by a sophisticated underlying engine that translates your stream definitions into a highly optimized data-flow graph known as a **Rete network**. Understanding the basics of this network can help you appreciate why Greynet is so efficient and how it handles data.

### Core Principles of Rete

The Rete algorithm (from the Latin word for "net") is designed to solve a many-to-many matching problem (many facts vs. many rules) efficiently. Its key principles are:

1. **Statefulness**: The network maintains the state of partial matches. When a new fact is added, it doesn't re-evaluate everything from scratch. It only calculates the *delta*—the new matches created or old matches invalidated by the change.
2. **Node Sharing**: If multiple rules share a common condition (e.g., `filter(lambda m: m.room == "Room A")`), the network builds the corresponding node for that condition only once and shares it across all relevant rule paths. This drastically reduces memory usage and redundant computation.
3. **Data-Driven Execution**: The flow of data (facts) through the network triggers the evaluation. There is no central loop that iterates through rules.

### Anatomy of the Network

The Rete network in Greynet is composed of different types of nodes, each corresponding to an operation in the Stream API.

```mermaid
graph TD
    subgraph Alpha Network (Single-Fact Conditions)
        direction LR
        F1[FromUniNode <br/> Meeting] --> P1(FilterNode <br/> room == 'A');
    end

    subgraph Beta Network (Multi-Fact Conditions)
        direction TB
        F2[FromUniNode <br/> Room] --> J1{JoinNode <br/> meeting.room == room.name};
        P1 -->|Left Input| J1;
        F2 -->|Right Input| J1;
        J1 --> G1[GroupNode <br/> by meeting.day];
        G1 --> S1[ScoringNode <br/> 'Too Many Meetings'];
    end

    style F1 fill:#cde4f9,stroke:#333
    style F2 fill:#cde4f9,stroke:#333
    style P1 fill:#d5e8d4,stroke:#333
    style J1 fill:#ffe6cc,stroke:#333
    style G1 fill:#ffe6cc,stroke:#333
    style S1 fill:#f8cecc,stroke:#333
```

*A simplified Rete graph showing different node types.*

#### The Alpha Network: Simple Conditions

These nodes handle conditions that apply to a single fact.

* #### `FromUniNode`
  
  The entry point for all facts into the network. There is one `FromUniNode` for each fact class you use in `builder.for_each()`. It takes a raw fact and wraps it in a `UniTuple`.

* #### `FilterNode`
  
  Represents a `stream.filter()` operation. It receives a tuple, applies its predicate, and propagates the tuple downstream only if the predicate returns `True`.

#### The Beta Network: Complex Conditions

These nodes handle relationships between multiple facts. They are the core of the network's stateful memory.

* #### `JoinNode`
  
  Corresponds to `stream.join()`. A `JoinNode` has two inputs (left and right) and maintains an indexed memory for each. When a tuple arrives on the left, it probes the right-side memory for matches based on the join key, creating new, larger tuples for each match. This is far more efficient than a nested loop over all facts.

* #### `ConditionalNode`
  
  Implements `if_exists` and `if_not_exists`. It works like a `JoinNode` but instead of creating new combined tuples, it simply checks for the existence of a match in its right-side memory and decides whether to propagate its original left-side tuple.

* #### `GroupNode`
  
  Represents `group_by`. This is a highly stateful node that maintains a mapping from group keys to **Collector** instances. When a fact arrives, it finds the correct collector, updates its state, and emits a new tuple with the key and the collector's latest result.

* #### Temporal & Sequential Nodes (`SlidingWindowNode`, `SequencePatternNode`)
  
  These are highly specialized beta-like nodes that implement the logic for `window()` and `sequence()` operations. They maintain complex internal state, such as sorted lists of events and active time windows, to efficiently detect temporal patterns.

#### Terminal Nodes

* #### `ScoringNode`
  
  The final node in a constraint's path. It is created by a `.penalize_*()` call. When a tuple reaches a `ScoringNode`, it signifies that all conditions for a constraint violation have been met. The node then:
  1. Executes the impact function to calculate the penalty score.
  2. Stores the tuple and its score as a "constraint match".
     The `session.get_score()` and `session.get_constraint_matches()` methods simply query the internal state of these `ScoringNode`s.

### Data Flow and Memory Management

* #### **Tuples**
  
  Data does not flow through the network as raw facts. It flows as **Tuple** objects (`UniTuple`, `BiTuple`, `TriTuple`, etc.). A tuple represents a partial match for a rule. For example, a `BiTuple` that has passed through a `JoinNode` represents a successful pairing of two initial facts.

* #### **The Scheduler**
  
  To avoid redundant work, Greynet does not process changes instantly. Insertions, retractions, and updates are placed in a queue managed by the `BatchScheduler`. When `session.flush()` is called (or triggered by `get_score()`), the scheduler processes all pending changes in an orderly fashion, ensuring that each change is propagated through the network exactly once.

* #### **Tuple Pooling**
  
  Creating and destroying thousands of `Tuple` objects can be slow due to memory allocation overhead. Greynet uses a `TuplePool` to mitigate this. When a tuple is no longer needed (e.g., a fact is retracted and its corresponding match is invalidated), the tuple object is not destroyed but is reset and returned to the pool for later reuse. This significantly improves performance in dynamic scenarios with many insertions and retractions.

By abstracting this intricate network behind the clean Stream API, Greynet offers the best of both worlds: a simple, declarative interface for rule definition and a highly efficient, stateful execution engine for high-performance evaluation.

***

This concludes the Greynet Reference Manual. You now have a comprehensive understanding of the engine, from its high-level concepts down to its internal workings.
