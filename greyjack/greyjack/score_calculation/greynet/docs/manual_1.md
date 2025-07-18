Of course. Here is a comprehensive, top-down guide to the Greynet library, crafted from the provided source code.

## Greynet: The Definitive Manual

Welcome to the comprehensive guide for Greynet, a powerful, forward-chaining rule engine for Python. Greynet is designed for complex event processing (CEP) and sophisticated constraint satisfaction problems, enabling you to define declarative rules that operate on streams of data in real-time.

This manual provides a top-down look at the library, from high-level concepts to the intricacies of its powerful API.

### 1. High-Level Overview

#### What is Greynet?

Greynet is a declarative rule engine inspired by the high-performance Rete algorithm. It allows you to define a set of **constraints** (rules) over a collection of data **facts**. When you insert, update, or retract facts, Greynet efficiently re-evaluates only the affected rules, calculates a **score** based on any violations, and provides a detailed breakdown of which facts matched which constraints.

Its core strengths are:

* **Declarative, Fluent API:** Define complex logic through a clean, chainable stream-processing API.
* **High Performance:** Under the hood, Greynet builds an optimized network of nodes, sharing common logic between rules to avoid redundant calculations.
* **Rich Feature Set:** Supports advanced operations including complex joins, aggregations, conditional logic (`if_exists`/`if_not_exists`), and powerful temporal pattern matching.
* **Dynamic and Incremental:** The engine reacts incrementally to data changes, making it suitable for real-time applications.

#### Core Concepts

Greynet's architecture can be visualized as a data processing pipeline.

```mermaid
graph TD
    A[Facts: Plain Python Objects] --> B(ConstraintBuilder);
    B --> C{Stream API: filter, join, group_by};
    C --> D[Constraint Definition: .penalize(...)];
    B -- build() --> E(Session);
    A -- insert()/retract() --> E;
    E -- Manages --> F((Rete Network));
    F -- Produces --> G[Score & Matches];
```

| Concept                 | Description                                                                                                                                                   |
|:----------------------- |:------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Fact**                | A plain Python object (often a `dataclass`) representing a piece of data in the system, like a `User` or an `Appointment`.                                    |
| **`ConstraintBuilder`** | The main factory class used to define all constraints and build the final `Session`.                                                                          |
| **`Stream`**            | A fluent, chainable object that represents a flow of data. You start with a stream of facts and apply operations like `filter()`, `join()`, and `group_by()`. |
| **`Constraint`**        | A rule defined by a decorated function. It is composed of a `Stream` that ends with a `.penalize()` call.                                                     |
| **`Session`**           | The runtime engine. You insert facts into the session, and it calculates the total score and provides a list of all constraint matches.                       |
| **Collectors**          | Powerful aggregation tools used with `group_by()` to calculate counts, sums, averages, lists, sets, and more.                                                 |

---

### 2. Getting Started: A Simple Example

Let's define a simple rule: "No user should have an 'admin' role".

#### Step 1: Define the Fact

A fact is just a simple Python object. A `dataclass` is often a good choice.

```python
from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    role: str
```

#### Step 2: Define the Constraint

Use the `ConstraintBuilder` and the `@builder.constraint` decorator to define your rule.

```python
from greynet import ConstraintBuilder

# 1. Initialize the builder
builder = ConstraintBuilder()

# 2. Define a constraint using the decorator
@builder.constraint("no_admin_users", default_weight=1.0)
def no_admins():
    # 3. Start a stream of facts from the User class
    return (builder.for_each(User)
            # 4. Filter for users where the role is 'admin'
            .filter(lambda user: user.role == 'admin')
            # 5. Penalize each match with a score of 100
            .penalize_hard(100)
    )
```

#### Step 3: Build and Use the Session

Build the session from the builder, insert facts, and check the score.

```python
# 1. Build the session
session = builder.build()

# 2. Create some facts
user1 = User(id=1, name="Alice", role="editor")
user2 = User(id=2, name="Bob", role="admin")
user3 = User(id=3, name="Charlie", role="admin")

# 3. Insert facts into the session
session.insert_batch([user1, user2, user3])

# 4. Get the total score
total_score = session.get_score()
print(f"Total Score: {total_score.hard_score}") # Output: Total Score: 200.0

# 5. Get a detailed breakdown of matches
matches = session.get_constraint_matches()
# `matches` will be a dictionary like:
# {
#   'no_admin_users': [
#     (score_object, (User(id=2, ...),)), 
#     (score_object, (User(id=3, ...),))
#   ]
# }
print(f"Found {len(matches.get('no_admin_users', []))} violations.") # Output: Found 2 violations.

# 6. Retract a fact and see the score update
session.retract(user2)
total_score_after_retract = session.get_score()
print(f"New Total Score: {total_score_after_retract.hard_score}") # Output: New Total Score: 100.0
```

---

### 3. The Fluent Stream API

The `Stream` object is the core of rule definition. All operations are chainable, allowing you to compose complex logic fluently.

A stream processes tuples of facts. A stream from `for_each` contains `UniTuple` (one fact). After a join, it might contain `BiTuple` (two facts), and so on.

#### Creating Streams

* **`builder.for_each(FactClass)`**
  This is the primary way to start a stream. It listens for all insertions of the specified `FactClass`.

#### Filtering

* **`.filter(lambda *facts: ...)`**
  Filters the stream, only allowing tuples that satisfy the predicate to pass through. The lambda receives the facts contained in the stream's tuple.
  
  ```python
  # UniTuple stream (1 fact)
  builder.for_each(Appointment).filter(lambda appt: appt.is_confirmed)
  
  # BiTuple stream (2 facts) from a join
  stream.filter(lambda user, appt: user.id == appt.user_id)
  ```

#### Joining

* **`.join(other_stream, joiner_type, left_key_func, right_key_func)`**
  Combines two streams into one. The resulting stream contains tuples with facts from both parents.
  **`JoinerType`**
  This enum specifies the join condition.
  
  | JoinerType               | Description                         |
  |:------------------------ |:----------------------------------- |
  | `EQUAL`                  | Keys are equal (most common).       |
  | `NOT_EQUAL`              | Keys are not equal.                 |
  | `LESS_THAN`              | Left key is less than right key.    |
  | `GREATER_THAN`           | Left key is greater than right key. |
  | `LESS_THAN_OR_EQUAL`     | ...                                 |
  | `GREATER_THAN_OR_EEQUAL` | ...                                 |
  
  **Example:** Find users who have scheduled appointments.
  
  ```python
  users = builder.for_each(User)
  appointments = builder.for_each(Appointment)
  
  users_with_appts = users.join(appointments,
      JoinerType.EQUAL,
      left_key_func=lambda user: user.id,
      right_key_func=lambda appt: appt.user_id
  )
  # The 'users_with_appts' stream now contains (user, appointment) pairs.
  ```

#### Conditional Existence

These are powerful tools for expressing rules based on the presence or absence of related data, without adding that data to the stream.

* **`.if_exists(other_stream, ...)`**
  Acts as a filter. A tuple from the main stream is propagated only if a matching tuple exists in the `other_stream`.
  **Example:** Find users who have at least one invoice.
  
  ```python
  users = builder.for_each(User)
  invoices = builder.for_each(Invoice)
  
  users_with_invoices = users.if_exists(invoices,
      left_key=lambda user: user.id,
      right_key=lambda invoice: invoice.customer_id
  )
  # The 'users_with_invoices' stream still contains only User facts.
  ```

* **`.if_not_exists(other_stream, ...)`**
  The opposite of `if_exists`. A tuple is propagated only if **no** matching tuple exists in the `other_stream`.
  **Example:** Find active users who have no overdue tasks.
  
  ```python
  active_users = builder.for_each(User).filter(lambda u: u.is_active)
  overdue_tasks = builder.for_each(Task).filter(lambda t: t.is_overdue)
  
  users_with_no_overdue_tasks = active_users.if_not_exists(overdue_tasks,
      left_key=lambda user: user.id,
      right_key=lambda task: task.assignee_id
  )
  ```

#### Aggregation

* **`.group_by(group_key_function, collector)`**
  This is one of Greynet's most powerful features. It groups facts from a stream by a key and applies a `Collector` to each group to produce an aggregate result.
  The output is a new stream of `BiTuple`s containing `(group_key, aggregate_result)`.
  **Example:** Count the number of tasks for each user.
  
  ```python
  from greynet import Collectors
  
  tasks = builder.for_each(Task)
  
  tasks_per_user = tasks.group_by(
      group_key_function=lambda task: task.assignee_id,
      collector_supplier=Collectors.count()
  )
  # The 'tasks_per_user' stream contains (user_id, count) pairs.
  ```

#### Transformation

* **`.map(lambda *facts: ...)`**
  Transforms each tuple in the stream into a new single-item `UniTuple`. This is a 1-to-1 transformation.

* **`.flat_map(lambda *facts: ...)`**
  Transforms each tuple into an iterable of new items. Each item from the iterable becomes a new `UniTuple` in the output stream. This is a 1-to-many transformation.
  **Example:** From a stream of `Order` facts, create a new stream of `OrderItem` facts.
  
  ```python
  orders = builder.for_each(Order)
  
  order_items = orders.flat_map(lambda order: order.items)
  # 'order_items' is now a stream of individual OrderItem facts.
  ```

---

### 4. The Collectors API

The `greynet.Collectors` namespace provides a rich set of tools for aggregation within a `group_by` operation.

#### Basic Aggregations

These collectors perform standard mathematical aggregations. Most require a mapping function to extract a numeric value from the fact.

* `Collectors.count()`: Counts items in a group.
* `Collectors.sum(lambda fact: fact.amount)`: Sums values.
* `Collectors.avg(lambda fact: fact.score)`: Calculates the average.
* `Collectors.min(lambda fact: fact.price)`: Finds the minimum value.
* `Collectors.max(lambda fact: fact.price)`: Finds the maximum value.
* `Collectors.stddev(lambda fact: fact.value)`: Calculates standard deviation.
* `Collectors.variance(lambda fact: fact.value)`: Calculates variance.

#### Collection Aggregations

These collectors gather facts into collections.

* `Collectors.to_list()`: Collects all facts in a group into a list.
* `Collectors.to_set()`: Collects unique facts into a set.
* `Collectors.distinct()`: Collects unique items into a list, preserving insertion order.

#### Advanced and Composite Collectors

* **`Collectors.compose({...})`**
  Performs multiple aggregations on the same group in a single pass for maximum efficiency. The result is a dictionary.
  
  ```python
  from greynet import Collectors
  
  stats_per_product = builder.for_each(Sale).group_by(
      lambda sale: sale.product_id,
      Collectors.compose({
          'sales_count': Collectors.count(),
          'total_revenue': Collectors.sum(lambda s: s.price),
          'avg_price': Collectors.avg(lambda s: s.price)
      })
  )
  # Output stream contains: 
  # (product_id, {'sales_count': 10, 'total_revenue': 550.0, ...})
  ```

* **`Collectors.filtering(predicate, downstream_collector)`**
  Filters items *within* a group before passing them to another collector.

* **`Collectors.mapping(mapper, downstream_collector)`**
  Maps items *within* a group before passing them to another collector.

#### Specialized Collectors

Greynet provides highly specialized collectors for complex pattern detection within groups.

* **`Collectors.consecutive_sequences(sequence_func, ...)`**
  Identifies runs of consecutive items. For example, finding consecutive login days for a user.
* **`Collectors.connected_ranges(start_func, end_func)`**
  Merges items that represent overlapping or adjacent ranges into single continuous ranges. Useful for scheduling problems to find blocks of busy/free time.
* **`Collectors.to_bloom_filter(...)`**
  Aggregates items into a `CountingBloomFilter` for efficient, probabilistic set membership tests.

---

### 5. Temporal and Sequential Patterns

Greynet includes first-class support for time-based rules, crucial for CEP scenarios.

#### Windowing

Windowing operations group facts based on their timestamps. You initiate windowing with `.window(time_extractor)` followed by a window type. The `time_extractor` is a function that returns a `datetime` object from your fact.

* **`.window(...).tumbling(size=timedelta)`**
  Creates fixed-size, non-overlapping windows. An event belongs to exactly one window.
* **`.window(...).sliding(size=timedelta, slide=timedelta)`**
  Creates fixed-size, overlapping windows. An event can belong to multiple windows.

**Example:** Count the number of logins every hour, updated every 5 minutes.

```python
from datetime import timedelta
from greynet import Collectors

logins_per_window = (builder.for_each(LoginEvent)
    .window(lambda event: event.timestamp)
    .sliding(size=timedelta(hours=1), slide=timedelta(minutes=5))
    .group_by(
        lambda window_start, events_in_window: window_start,
        Collectors.mapping(
            lambda ws, elist: len(elist), # Map the tuple to just the count
            Collectors.sum(lambda count: count) # Sum the counts
        )
    )
)
```

#### Sequence Detection

* **`.sequence(time_extractor, *steps, within=timedelta, allow_gaps=bool)`**
  This powerful feature detects when facts occur in a specific order within a time limit. It takes a series of predicates (`*steps`) that must be satisfied sequentially.

**Example:** Detect when a user adds an item to their cart, then views the checkout page, but does not complete the purchase within 10 minutes.

```python
from datetime import timedelta

# Define predicates for each step in the sequence
def is_add_to_cart(event): return event.type == 'ADD_TO_CART'
def is_view_checkout(event): return event.type == 'VIEW_CHECKOUT'

# Stream of sequences: (add_to_cart_event, view_checkout_event)
potential_abandonment = (builder.for_each(UserEvent)
    .sequence(
        lambda event: event.timestamp,
        is_add_to_cart,
        is_view_checkout,
        within=timedelta(minutes=10)
    )
)

# Stream of completed purchases
purchases = builder.for_each(UserEvent).filter(lambda e: e.type == 'PURCHASE')

# Final rule: penalize if the sequence occurs and a purchase does NOT.
abandoned_carts = potential_abandonment.if_not_exists(purchases,
    # Join on user ID
    left_key=lambda sequence: sequence[0].user_id, 
    right_key=lambda purchase: purchase.user_id
)
```

---

### 6. Scoring, Penalties, and Weights

Every constraint must end with a `.penalize()` call, which defines the score impact when the rule is matched.

#### Penalty Methods

* `.penalize_hard(penalty)`
* `.penalize_medium(penalty)`
* `.penalize_soft(penalty)`
* `.penalize_simple(penalty)`

These correspond to different fields in the final score object, allowing you to create multi-objective scoring functions (e.g., minimizing hard violations first, then soft).

The `penalty` argument can be a static number or a `lambda` function that receives the matched facts, allowing for dynamic penalties.

```python
# Static penalty
.penalize_soft(50)

# Dynamic penalty based on the fact
.penalize_soft(lambda order: order.value * 0.1) 
```

#### Dynamic Weights

You can change the "importance" of a constraint at runtime without rebuilding the session.

1. **Instantiate `ConstraintWeights`** and pass it to the builder.
2. Use `session.update_constraint_weight(constraint_id, new_weight)` to change a weight. The engine will automatically and efficiently recalculate the scores for that constraint.

```python
# --- Definition ---
from greynet import ConstraintWeights

weights = ConstraintWeights()
builder = ConstraintBuilder(weights=weights)

@builder.constraint("expensive_order", default_weight=1.0)
def expensive_order_rule():
    return (builder.for_each(Order)
            .filter(lambda o: o.value > 1000)
            .penalize_soft(lambda o: o.value / 100)
    )

# --- Runtime ---
session = builder.build()
session.insert(Order(value=2000))
print(session.get_score().soft_score) # Output: 20.0 ( (2000/100) * 1.0 )

# Now, double the importance of this rule
session.update_constraint_weight("expensive_order", 2.0)
print(session.get_score().soft_score) # Output: 40.0 ( (2000/100) * 2.0 )
```

---

### 7. Low-Level Architecture

While you primarily interact with the high-level API, understanding the underlying structure can be helpful.

* **Rete Network:** When you call `builder.build()`, Greynet translates your stream definitions into a network of nodes (`FromNode`, `FilterNode`, `JoinNode`, etc.).
* **Node Sharing:** This is a key optimization. If two different constraints share a common logical path (e.g., they both start with `builder.for_each(User).filter(...)`), the engine builds the nodes for that path only once and shares them.
* **Tuples:** As facts propagate through the network, they are wrapped in `UniTuple`, `BiTuple`, etc. These internal objects track the state of a match.
* **Indexing:** Join nodes use internal hash indexes (for `EQUAL` joins) and sorted-list indexes (for range joins) to find matching tuples efficiently, avoiding full scans.
* **Scheduler:** A `BatchScheduler` collects all changes (insertions, retractions) and processes them in a queue, ensuring that changes propagate through the network in a consistent order.
* **Tuple Pooling:** To reduce garbage collection overhead in high-throughput scenarios, Greynet uses an object pool (`TuplePool`) to reuse its internal tuple objects.

Of course. Here is the continuation of the Greynet manual, focusing on a detailed API reference and advanced usage patterns.

### 8. The Greynet API Reference

This section provides a quick reference for the primary classes and methods you will use when working with Greynet.

#### `ConstraintBuilder`

The main entry point for defining rules and building a session.

| Method                                     | Description                                                                                                                                                                               |
|:------------------------------------------ |:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`__init__(name, score_class, weights)`** | Initializes the builder. `score_class` lets you define custom score objects (e.g., `HardSoftScore`), and `weights` accepts a `ConstraintWeights` instance for dynamic penalty management. |
| **`constraint(id, weight)`**               | A decorator for a function that defines a single rule. Assigns a unique ID and a default weight to the constraint.                                                                        |
| **`for_each(FactClass)`**                | Starts a new `Stream` of data, listening for insertions of the specified `FactClass`. This is the most common way to begin a rule definition.                                             |
| **`build(**kwargs)`**                      | Compiles all the defined `@constraint` functions into an optimized Rete network and returns an executable `Session` instance.                                                             |

#### `Session`

The runtime engine that manages facts and calculates scores.

| Method                                     | Description                                                                                                                                                                                          |
|:------------------------------------------ |:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`insert(fact)`**                         | Inserts a single fact into the engine and immediately processes the consequences.                                                                                                                    |
| **`retract(fact)`**                        | Retracts a single fact from the engine and immediately processes the consequences.                                                                                                                   |
| **`insert_batch(facts)`**                  | Inserts an iterable of facts. More efficient than multiple `insert()` calls.                                                                                                                         |
| **`retract_batch(facts)`**                 | Retracts an iterable of facts.                                                                                                                                                                       |
| **`flush()`**                              | Processes all pending insertions and retractions in the queue. This is called automatically by `get_score()` and `get_constraint_matches()`.                                                         |
| **`clear()`**                              | Retracts all facts from the session, effectively resetting it to an empty state.                                                                                                                     |
| **`get_score()`**                          | Flushes the queue and returns the total aggregated score object for the current state of the facts.                                                                                                  |
| **`get_constraint_matches()`**             | Flushes the queue and returns a `dict` mapping each `constraint_id` to a list of its violations. Each violation is a tuple containing the score object and the fact(s) that caused it.               |
| **`update_constraint_weight(id, weight)`** | Updates the weight multiplier for a constraint at runtime and triggers a re-calculation of all scores for that constraint. Requires a `ConstraintWeights` object to have been passed to the builder. |

#### `Stream`

The fluent, chainable object for defining data processing logic.

| Method                                           | Description                                                                                                                   |
|:------------------------------------------------ |:----------------------------------------------------------------------------------------------------------------------------- |
| **`.filter(predicate)`**                         | Filters tuples based on a boolean predicate.                                                                                  |
| **`.join(other, joiner, left_key, right_key)`**  | Joins with another stream on a key.                                                                                           |
| **`.if_exists(other, left_key, right_key)`**     | Propagates a tuple only if a match exists in the other stream.                                                                |
| **`.if_not_exists(other, left_key, right_key)`** | Propagates a tuple only if **no** match exists in the other stream.                                                           |
| **`.group_by(key_func, collector)`**             | Groups tuples by a key and aggregates each group using a `Collector`.                                                         |
| **`.map(mapper_func)`**                          | Performs a 1-to-1 transformation of each tuple in the stream.                                                                 |
| **`.flat_map(mapper_func)`**                     | Performs a 1-to-many transformation of each tuple in the stream.                                                              |
| **`.window(time_extractor)`**                    | Initiates a temporal windowing operation. Must be followed by `.sliding()` or `.tumbling()`.                                  |
| **`.sequence(time_ext, *steps, within, ...)`**   | Detects ordered sequences of facts within a time window.                                                                      |
| **`.penalize_{type}(penalty)`**                  | Terminates a stream definition, marking it as part of a constraint. The `penalty` can be a static value or a lambda function. |

#### `Collectors`

A namespace of aggregation tools for use with `.group_by()`.

| Collector                                | Description                                          |
|:---------------------------------------- |:---------------------------------------------------- |
| `count()`                                | Counts items in the group.                           |
| `sum(mapper)`                            | Sums the numeric value returned by the mapper.       |
| `avg(mapper)`                            | Averages the numeric value returned by the mapper.   |
| `min(mapper)` / `max(mapper)`            | Finds the min/max value.                             |
| `to_list()` / `to_set()`                 | Aggregates items into a list or set.                 |
| `compose({key: collector, ...})`         | Performs multiple aggregations simultaneously.       |
| `filtering(predicate, downstream)`       | Pre-filters items within a group before aggregating. |
| `consecutive_sequences(seq_func)`        | Finds and groups consecutive items.                  |
| `connected_ranges(start_func, end_func)` | Finds and merges overlapping/adjacent time ranges.   |

---

### 9. Advanced Patterns & Use Cases

This section demonstrates how to combine the features of Greynet to solve more complex, real-world problems.

#### Use Case: Resource Scheduling

Let's model a meeting room booking system. The goal is to prevent double-bookings and to enforce a company policy that meetings should be at least 30 minutes long.

**1. Define the Facts**

We need a fact to represent a booking request.

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class BookingRequest:
    request_id: str
    room_id: str
    start_time: datetime
    end_time: datetime

    @property
    def duration_minutes(self) -> float:
        return (self.end_time - self.start_time).total_seconds() / 60
```

**2. Define the Constraints**

We'll use `Patterns` for the complex overlap detection and a simple `filter` for the duration policy.

```python
from greynet import ConstraintBuilder, JoinerType, Patterns, Collectors

builder = ConstraintBuilder()
patterns = Patterns(builder) # Helper for common patterns

# Constraint 1: Prevent overlapping bookings in the same room.
# This is a critical failure, so we use penalize_hard.
@builder.constraint("overlapping_bookings")
def find_overlapping_bookings():
    # A self-join on BookingRequest is needed to compare every request with every other request.
    return (builder.for_each(BookingRequest)
            # Join requests that are for the same room
            .join(builder.for_each(BookingRequest),
                JoinerType.EQUAL,
                lambda req: req.room_id,
                lambda req: req.room_id)
            # Filter 1: Ensure we don't match a request with itself (req1.id < req2.id is a common trick)
            .filter(lambda req1, req2: req1.request_id < req2.request_id)
            # Filter 2: The core overlap logic. Two ranges (s1, e1) and (s2, e2) overlap if 
            # the start of one is before the end of the other, and vice versa.
            # Simplified: max(start1, start2) < min(end1, end2)
            .filter(lambda req1, req2: max(req1.start_time, req2.start_time) < min(req1.end_time, req2.end_time))
            # Penalize each pair of overlapping bookings.
            .penalize_hard(1000)
    )

# Constraint 2: Meetings should be at least 30 minutes long.
# This is a soft policy, so we use penalize_soft.
@builder.constraint("meeting_too_short")
def find_short_meetings():
    return (builder.for_each(BookingRequest)
            # Find all bookings shorter than 30 minutes.
            .filter(lambda req: req.duration_minutes < 30)
            # The penalty can be dynamic, penalizing more for shorter meetings.
            .penalize_soft(lambda req: 30 - req.duration_minutes)
    )
```

**3. Run the Session**

Now, we build the session and insert some bookings to see the rules in action.

```python
# Build the session
scheduler_session = builder.build()

# Create some bookings
bookings = [
    # A valid booking
    BookingRequest("B1", "Room-101", datetime(2025, 7, 16, 9, 0), datetime(2025, 7, 16, 10, 0)),
    # Another valid booking in a different room
    BookingRequest("B2", "Room-102", datetime(2025, 7, 16, 9, 0), datetime(2025, 7, 16, 10, 0)),
    # This booking overlaps with B1
    BookingRequest("B3", "Room-101", datetime(2025, 7, 16, 9, 30), datetime(2025, 7, 16, 10, 30)),
    # This booking is too short (15 mins)
    BookingRequest("B4", "Room-102", datetime(2025, 7, 16, 11, 0), datetime(2025, 7, 16, 11, 15)),
]

# Insert and check score
scheduler_session.insert_batch(bookings)
score = scheduler_session.get_score()

print(f"Hard Score (Overlaps): {score.hard_score}")
# Expected Output: Hard Score (Overlaps): 1000.0 (from B1 and B3 overlapping)

print(f"Soft Score (Short Meetings): {score.soft_score}")
# Expected Output: Soft Score (Short Meetings): 15.0 (from B4 being 15 mins too short)

# Get the specific violations
matches = scheduler_session.get_constraint_matches()
overlapping_pair = matches["overlapping_bookings"][0][1] # The tuple of facts
short_meeting = matches["meeting_too_short"][0][1][0] # The single fact

print(f"Overlap detected between {overlapping_pair[0].request_id} and {overlapping_pair[1].request_id}")
print(f"Short meeting detected: {short_meeting.request_id}")
```

This example illustrates how separate constraints can work together to validate a complex system, combining `join`, `filter`, and different penalty levels to enforce both critical rules and soft policies.
