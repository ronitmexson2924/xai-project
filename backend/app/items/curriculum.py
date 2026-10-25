"""Curriculum concepts and misconceptions registry for DSA.

Owner: Mit.
Provides concept definitions, concept cards, and cataloged misconceptions
across all 8 DSA clusters defined in PROJECT_BRIEF.md (D1).
"""

# ruff: noqa: E501

from typing import NamedTuple

from app.contracts.graph import Concept, ConceptCard, Misconception


class ConceptWithMisconceptions(NamedTuple):
    concept: Concept
    misconceptions: list[Misconception]


# Comprehensive catalog of concepts and cataloged misconceptions across 8 DSA clusters
DSA_CURRICULUM: list[ConceptWithMisconceptions] = [
    # -------------------------------------------------------------------------
    # Cluster 1: basics
    # -------------------------------------------------------------------------
    ConceptWithMisconceptions(
        concept=Concept(
            id="loops",
            name="Loops & Iteration",
            cluster="basics",
            difficulty=1,
            description="Repeating statements while a termination predicate holds.",
            card=ConceptCard(
                definition="A loop runs code repeatedly while a termination condition holds.",
                key_idea="Every loop needs a condition that eventually changes state to terminate.",
                worked_example="for i in range(3): print(i)",
                pitfall="Off-by-one: range(3) stops before 3.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="loops-off-by-one",
                concept_id="loops",
                description="Assumes range(n) includes n or miscalculates bounds.",
            ),
            Misconception(
                id="loops-never-terminate",
                concept_id="loops",
                description="Forgets to update loop variables, causing infinite loop.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="nested-loops",
            name="Nested Loops",
            cluster="basics",
            difficulty=2,
            description="Loops executing inside the body of an outer loop.",
            card=ConceptCard(
                definition="An inner loop executes its full cycle for every single step of the outer loop.",
                key_idea="Total iterations multiply: outer iterations * inner iterations.",
                worked_example="for i in range(2):\n    for j in range(3): print(i, j)",
                pitfall="Confusing inner and outer index variables.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="nested-loops-add-not-mult",
                concept_id="nested-loops",
                description="Believes total executions add (N + M) instead of multiply (N * M).",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="time-complexity-intro",
            name="Time Complexity Basics",
            cluster="basics",
            difficulty=2,
            description="Asymptotic growth rate of running time in Big-O notation.",
            card=ConceptCard(
                definition="Big-O characterizes the upper bound of operational steps as input N scales.",
                key_idea="Ignore constant multipliers and lower-order terms as N approaches infinity.",
                worked_example="Single pass over N elements is O(N); nested pass is O(N^2).",
                pitfall="Treating O(1) as fast in seconds rather than invariant to input size.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="time-comp-drop-high-order",
                concept_id="time-complexity-intro",
                description="Keeps constants and drops the highest order polynomial term.",
            ),
            Misconception(
                id="time-comp-line-count-equals-time",
                concept_id="time-complexity-intro",
                description="Equates line count of source code directly to asymptotic complexity.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="space-complexity-intro",
            name="Space Complexity Basics",
            cluster="basics",
            difficulty=2,
            description="Memory overhead required by an algorithm relative to input size.",
            card=ConceptCard(
                definition="Auxiliary space measures extra working memory beyond the input itself.",
                key_idea="Creating a new array of size N requires O(N) auxiliary space.",
                worked_example="Reversing in place uses O(1) auxiliary space.",
                pitfall="Confusing input space with auxiliary space.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="space-comp-include-input-as-aux",
                concept_id="space-complexity-intro",
                description="Counts read-only input array towards auxiliary memory footprint.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="conditional-invariants",
            name="Conditional Invariants",
            cluster="basics",
            difficulty=1,
            description="Branching logic and assertions that remain invariant.",
            card=ConceptCard(
                definition="Branching routes execution based on Boolean predicates.",
                key_idea="Mutual exclusion guarantees exactly one branch runs in an if-elif-else chain.",
                worked_example="if x > 0: pos() else: non_pos()",
                pitfall="Assuming independent if statements are mutually exclusive.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="cond-chain-multi-execute",
                concept_id="conditional-invariants",
                description="Expects multiple elif branches to execute if their conditions are true.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="variables-and-scope",
            name="Variable Scope & Mutation",
            cluster="basics",
            difficulty=1,
            description="Lifetime and accessibility of identifiers and mutable references.",
            card=ConceptCard(
                definition="Scope determines identifier visibility; mutable structures mutate in place.",
                key_idea="Reassigning a pointer differs from modifying the object it points to.",
                worked_example="arr.append(1) mutates; arr = [1] rebinds the reference.",
                pitfall="Unexpected side-effects from passing mutable lists to functions.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="scope-rebinding-modifies-caller",
                concept_id="variables-and-scope",
                description="Believes reassigning a parameter variable rebinds the caller reference.",
            ),
        ],
    ),
    # -------------------------------------------------------------------------
    # Cluster 2: arrays-strings
    # -------------------------------------------------------------------------
    ConceptWithMisconceptions(
        concept=Concept(
            id="array-indexing",
            name="Array Indexing & Bounds",
            cluster="arrays-strings",
            difficulty=1,
            description="Direct zero-indexed contiguous memory access.",
            card=ConceptCard(
                definition="Arrays store elements sequentially in contiguous memory blocks.",
                key_idea="Index arithmetic calculates memory offset in O(1) time.",
                worked_example="arr[0] gets first element; arr[len(arr)-1] gets last.",
                pitfall="Accessing index len(arr) raises IndexError.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="array-1-based-indexing",
                concept_id="array-indexing",
                description="Assumes arrays start at index 1 instead of index 0.",
            ),
            Misconception(
                id="array-out-of-bounds",
                concept_id="array-indexing",
                description="Assumes accessing index N of an N-element array returns None or 0.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="two-pointers-technique",
            name="Two Pointers Technique",
            cluster="arrays-strings",
            difficulty=2,
            description="Navigating an array using two simultaneous converging indices.",
            card=ConceptCard(
                definition="Two pointers traverse a sequence from both ends towards each other or at varying speeds.",
                key_idea="Monotonic sorted order guarantees eliminating impossible candidate spaces.",
                worked_example="low = 0, high = n - 1; increment low or decrement high based on sum.",
                pitfall="Moving both pointers simultaneously when only one condition is met.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="two-pointers-requires-sorted",
                concept_id="two-pointers-technique",
                description="Applies opposite-direction two pointers on unsorted arrays expecting monotonic sums.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="sliding-window",
            name="Sliding Window",
            cluster="arrays-strings",
            difficulty=3,
            description="Tracking a contiguous subsegment with moving window boundaries.",
            card=ConceptCard(
                definition="A sliding window maintains a contiguous subsegment by expanding right and shrinking left.",
                key_idea="Reuses computation from overlapping subsegments to avoid O(N^2) recalculations.",
                worked_example="Add arr[right] to sum; while sum > target: subtract arr[left]; left += 1.",
                pitfall="Resetting window from scratch instead of shrinking the left boundary.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="sliding-window-discontinuous",
                concept_id="sliding-window",
                description="Assumes sliding window can skip elements within its active boundary.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="prefix-sums",
            name="Prefix Sums",
            cluster="arrays-strings",
            difficulty=2,
            description="Precomputing cumulative sums to answer range sum queries in O(1).",
            card=ConceptCard(
                definition="prefix[i] stores the sum of all elements from index 0 up to i.",
                key_idea="Range sum query [L, R] = prefix[R] - prefix[L - 1].",
                worked_example="P = [0, 2, 5, 9]; sum(1..2) = P[3] - P[1] = 9 - 2 = 7.",
                pitfall="Forgetting prefix base value 0, causing off-by-one when L=0.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="prefix-sums-off-by-one",
                concept_id="prefix-sums",
                description="Subtracts prefix[L] instead of prefix[L - 1] for inclusive range [L, R].",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="string-immutability",
            name="String Immutability & Manipulation",
            cluster="arrays-strings",
            difficulty=2,
            description="Handling memory implications of immutable string representations.",
            card=ConceptCard(
                definition="Immutable strings cannot be modified in place; concatenation copies characters.",
                key_idea="Repeated string += concatenation in a loop takes O(N^2) time; join takes O(N).",
                worked_example="''.join(char_list) is O(N) whereas s += c in a loop is O(N^2).",
                pitfall="Assuming s[i] = 'a' modifies the string in place.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="string-concat-is-constant-time",
                concept_id="string-immutability",
                description="Believes string concatenation is O(1) time regardless of length.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="in-place-array-modification",
            name="In-Place Array Modification",
            cluster="arrays-strings",
            difficulty=2,
            description="Overwriting array contents using write pointers without extra space.",
            card=ConceptCard(
                definition="In-place modification overwrites valid elements using read and write pointer indices.",
                key_idea="Maintain write_index <= read_index so unprocessed data is never overwritten.",
                worked_example="if arr[read] != val: arr[write] = arr[read]; write += 1.",
                pitfall="Overwriting elements before their values have been inspected.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="in-place-overwrites-uninspected",
                concept_id="in-place-array-modification",
                description="Increments write pointer faster than read pointer, clobbering input.",
            ),
        ],
    ),
    # -------------------------------------------------------------------------
    # Cluster 3: linked-structures
    # -------------------------------------------------------------------------
    ConceptWithMisconceptions(
        concept=Concept(
            id="singly-linked-list-node",
            name="Singly Linked List Nodes",
            cluster="linked-structures",
            difficulty=2,
            description="Node structures containing a value and next reference pointer.",
            card=ConceptCard(
                definition="A linked list node stores data and a pointer reference to the subsequent node.",
                key_idea="Nodes are scattered non-contiguously across memory connected by reference pointers.",
                worked_example="class Node: val, next = None. head = Node(1); head.next = Node(2)",
                pitfall="Assuming node.next is a node instead of checking if it is None.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="linked-list-random-access",
                concept_id="singly-linked-list-node",
                description="Believes linked lists support O(1) random indexing like arrays.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="linked-list-traversal",
            name="Linked List Traversal",
            cluster="linked-structures",
            difficulty=2,
            description="Iterating through pointer chains until reaching the tail sentinel.",
            card=ConceptCard(
                definition="Traversal steps from current = current.next until current is None.",
                key_idea="Always verify current is not None before dereferencing current.next.",
                worked_example="curr = head; while curr: print(curr.val); curr = curr.next",
                pitfall="AttributeError: 'NoneType' object has no attribute 'next'.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="linked-list-deref-null",
                concept_id="linked-list-traversal",
                description="Checks curr.next.val without first ensuring curr is not None.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="linked-list-insertion",
            name="Linked List Insertion",
            cluster="linked-structures",
            difficulty=2,
            description="Re-wiring pointers to insert a new node into an existing chain.",
            card=ConceptCard(
                definition="Insertion updates new_node.next = prev.next, then prev.next = new_node.",
                key_idea="Wiring order matters: link new node to successor first to avoid losing chain.",
                worked_example="new_node.next = curr.next; curr.next = new_node",
                pitfall="Overwriting curr.next before linking new_node.next orphans the rest of the list.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="linked-list-orphan-chain",
                concept_id="linked-list-insertion",
                description="Sets curr.next = new_node first, accidentally losing reference to the tail.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="linked-list-deletion",
            name="Linked List Deletion",
            cluster="linked-structures",
            difficulty=2,
            description="Bypassing a target node by pointing predecessor to successor.",
            card=ConceptCard(
                definition="Deletion bypasses a node via prev.next = target.next.",
                key_idea="Use a dummy pre-head node to handle edge cases like deleting the head node.",
                worked_example="dummy.next = head; prev = dummy; while curr: if curr.val == val: prev.next = curr.next",
                pitfall="Losing the new head pointer when deleting head.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="linked-list-delete-without-prev",
                concept_id="linked-list-deletion",
                description="Attempts to delete a node while only holding a pointer to that node.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="fast-slow-pointers",
            name="Fast & Slow Pointers (Floyd's Cycle)",
            cluster="linked-structures",
            difficulty=3,
            description="Two pointers moving at different speeds to detect cycles or find midpoints.",
            card=ConceptCard(
                definition="Slow advances 1 step while fast advances 2 steps per iteration.",
                key_idea="In a cyclic list, the relative distance between fast and slow decreases by 1 each step.",
                worked_example="while fast and fast.next: slow = slow.next; fast = fast.next.next; if slow == fast: cycle()",
                pitfall="Failing to check fast.next before accessing fast.next.next.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="floyd-skip-null-check",
                concept_id="fast-slow-pointers",
                description="Only checks `while fast:` without `fast.next`, triggering null dereference.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="doubly-linked-list",
            name="Doubly Linked Lists",
            cluster="linked-structures",
            difficulty=3,
            description="Bidirectional pointer navigation with prev and next attributes.",
            card=ConceptCard(
                definition="Nodes store pointers to both predecessor (prev) and successor (next).",
                key_idea="Allows O(1) removal given a direct reference to the target node.",
                worked_example="node.prev.next = node.next; node.next.prev = node.prev",
                pitfall="Forgetting to update backward prev pointer on adjacent nodes.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="doubly-linked-forget-prev",
                concept_id="doubly-linked-list",
                description="Updates next pointers but leaves prev pointers stale, corrupting reverse iteration.",
            ),
        ],
    ),
    # -------------------------------------------------------------------------
    # Cluster 4: recursion
    # -------------------------------------------------------------------------
    ConceptWithMisconceptions(
        concept=Concept(
            id="recursion-base-case",
            name="Recursion: Base Case",
            cluster="recursion",
            difficulty=2,
            description="The terminating condition that halts recursive call cascades.",
            card=ConceptCard(
                definition="A base case is a direct input condition answered without further recursive calls.",
                key_idea="Each recursive step must strictly reduce the problem size towards a base case.",
                worked_example="def fact(n): return 1 if n == 0 else n * fact(n - 1)",
                pitfall="Missing or unreachable base case triggers RecursionError (stack overflow).",
            ),
        ),
        misconceptions=[
            Misconception(
                id="recursion-no-base-case",
                concept_id="recursion-base-case",
                description="Believes recursion automatically stops on its own without explicit base case.",
            ),
            Misconception(
                id="recursion-base-case-unreachable",
                concept_id="recursion-base-case",
                description="Moves in the wrong direction (e.g. n + 1 towards 0), never reaching base case.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="recursive-call-stack",
            name="Recursive Call Stack",
            cluster="recursion",
            difficulty=3,
            description="Memory stack frames storing local execution context for pending calls.",
            card=ConceptCard(
                definition="Each call pushes an activation record with local variables onto the call stack.",
                key_idea="Max stack depth is bounded by recursion depth, requiring O(D) memory.",
                worked_example="fact(3) pushes fact(2), fact(1), fact(0); resolves bottom-up.",
                pitfall="Assuming recursive calls execute concurrently rather than sequentially.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="recursion-shared-local-vars",
                concept_id="recursive-call-stack",
                description="Believes local variables in recursive invocations overwrite each other.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="divide-and-conquer",
            name="Divide and Conquer",
            cluster="recursion",
            difficulty=3,
            description="Partitioning problems into non-overlapping subproblems and combining results.",
            card=ConceptCard(
                definition="Divide problem into independent subproblems, solve recursively, and combine.",
                key_idea="Master theorem: T(N) = aT(N/b) + f(N) governs asymptotic complexity.",
                worked_example="Merge sort divides array in half, sorts each half, and merges in O(N).",
                pitfall="Doing too much work in the combine step, ruining logarithmic depth benefit.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="divide-conquer-overlapping-subproblems",
                concept_id="divide-and-conquer",
                description="Applies divide and conquer to heavily overlapping subproblems without memoization.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="tree-recursion",
            name="Tree & Branching Recursion",
            cluster="recursion",
            difficulty=3,
            description="Recursive functions making two or more branching self-calls per frame.",
            card=ConceptCard(
                definition="Branching recursion calls self multiple times, forming an execution tree.",
                key_idea="Total calls grow exponentially O(b^d) unless subproblems are pruned.",
                worked_example="fib(n) = fib(n - 1) + fib(n - 2) spawns 2^n operations without cache.",
                pitfall="Exponential time explosion from re-computing identical subtrees.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="tree-recursion-linear-time",
                concept_id="tree-recursion",
                description="Assumes two recursive calls per step runs in O(N) rather than O(2^N).",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="backtracking-basics",
            name="Backtracking Exploration",
            cluster="recursion",
            difficulty=4,
            description="Systematic depth-first search that undoes state choices upon dead ends.",
            card=ConceptCard(
                definition="Backtracking builds candidates incrementally and abandons (backtracks) invalid paths.",
                key_idea="Always revert the state change after the recursive call returns.",
                worked_example="path.append(choice); backtrack(next); path.pop()  # undo choice",
                pitfall="Forgetting to revert the choice before backtracking to the parent frame.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="backtracking-forget-undo",
                concept_id="backtracking-basics",
                description="Forgets to undo state changes, bleeding choices into sibling exploration paths.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="tail-recursion",
            name="Tail Call Recursion",
            cluster="recursion",
            difficulty=3,
            description="Recursive calls that are the very final action performed in the function.",
            card=ConceptCard(
                definition="A tail-recursive call has no pending computations after the call returns.",
                key_idea="Can be transformed into an iterative loop with O(1) stack frames.",
                worked_example="def fact_tail(n, acc=1): return acc if n==0 else fact_tail(n-1, n*acc)",
                pitfall="Confusing return n * fact(n - 1) (not tail) with return fact_tail(n - 1, acc).",
            ),
        ),
        misconceptions=[
            Misconception(
                id="tail-call-pending-mult",
                concept_id="tail-recursion",
                description="Believes `return n * f(n-1)` is tail recursive despite pending multiplication.",
            ),
        ],
    ),
    # -------------------------------------------------------------------------
    # Cluster 5: sorting-searching
    # -------------------------------------------------------------------------
    ConceptWithMisconceptions(
        concept=Concept(
            id="linear-search",
            name="Linear Search",
            cluster="sorting-searching",
            difficulty=1,
            description="Sequentially scanning elements from beginning to end.",
            card=ConceptCard(
                definition="Linear search checks every element sequentially until target is found or list ends.",
                key_idea="Works on unsorted collections in O(N) worst-case time.",
                worked_example="for i, val in enumerate(arr): if val == target: return i",
                pitfall="Stopping early before examining all items when target is absent.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="linear-search-requires-sorted",
                concept_id="linear-search",
                description="Believes linear search requires sorted data to work.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="binary-search-bounds",
            name="Binary Search Bounds",
            cluster="sorting-searching",
            difficulty=2,
            description="Maintaining low and high boundary pointers over a sorted range.",
            card=ConceptCard(
                definition="Binary search maintains low and high pointers enclosing the search space.",
                key_idea="Update low = mid + 1 or high = mid - 1 to guarantee progress each iteration.",
                worked_example="while low <= high: mid = (low + high) // 2",
                pitfall="Using high = mid with while low <= high can cause an infinite loop.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="binary-search-infinite-loop",
                concept_id="binary-search-bounds",
                description="Sets high = mid or low = mid, stalling pointer progress on 2-element intervals.",
            ),
            Misconception(
                id="binary-search-on-unsorted",
                concept_id="binary-search-bounds",
                description="Applies binary search to unsorted collections, discarding valid candidates.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="binary-search-midpoint",
            name="Binary Search Midpoint Calculation",
            cluster="sorting-searching",
            difficulty=2,
            description="Calculating intermediate pivot indices without integer overflow.",
            card=ConceptCard(
                definition="Midpoint calculation partitions the active interval into two equal halves.",
                key_idea="In bounded integer arithmetic, use low + (high - low) // 2 to avoid overflow.",
                worked_example="mid = low + (high - low) // 2",
                pitfall="Floating point division instead of integer floor division.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="bsearch-float-division",
                concept_id="binary-search-midpoint",
                description="Uses `/` instead of `//`, generating non-integer indices in language runtimes.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="bubble-sort-invariant",
            name="Bubble Sort Invariant",
            cluster="sorting-searching",
            difficulty=2,
            description="Repeatedly swapping adjacent inverted elements to float maxima to tail.",
            card=ConceptCard(
                definition="Bubble sort swaps adjacent out-of-order elements across repeated passes.",
                key_idea="After pass k, the k largest elements are guaranteed in their final sorted positions.",
                worked_example="for i in range(n): for j in range(n - i - 1): if arr[j] > arr[j+1]: swap()",
                pitfall="Continuing passes even when no swaps occurred during an entire scan.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="bubble-sort-is-linear",
                concept_id="bubble-sort-invariant",
                description="Believes bubble sort is O(N) in the general worst/average case.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="merge-sort-merge-step",
            name="Merge Sort: Merging Subarrays",
            cluster="sorting-searching",
            difficulty=3,
            description="Combining two sorted subarrays into a single sorted array in O(N).",
            card=ConceptCard(
                definition="The merge step compares headers of two sorted slices and appends the smaller.",
                key_idea="Two sorted arrays of size N and M can be merged in O(N + M) time.",
                worked_example="while i < len(L) and j < len(R): take smaller; copy remaining tail.",
                pitfall="Forgetting to append the remaining elements when one sub-array exhausts first.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="merge-sort-in-place-naive",
                concept_id="merge-sort-merge-step",
                description="Assumes standard merge step runs in O(1) auxiliary space without extra buffer.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="quick-sort-partition",
            name="Quick Sort Partitioning",
            cluster="sorting-searching",
            difficulty=3,
            description="Rearranging array around a pivot such that left <= pivot < right.",
            card=ConceptCard(
                definition="Partitioning chooses a pivot and places smaller elements left, larger elements right.",
                key_idea="The pivot lands in its absolute sorted position at the end of the partition step.",
                worked_example="Lomuto partition iterates with boundary index i; swaps when arr[j] < pivot.",
                pitfall="Worst-case O(N^2) time occurs on already-sorted arrays with naive first-element pivot.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="quicksort-always-nlogn",
                concept_id="quick-sort-partition",
                description="Believes quick sort is O(N log N) worst-case under naive pivot choices.",
            ),
        ],
    ),
    # -------------------------------------------------------------------------
    # Cluster 6: trees
    # -------------------------------------------------------------------------
    ConceptWithMisconceptions(
        concept=Concept(
            id="binary-tree-traversal-preorder",
            name="Binary Tree: Preorder Traversal",
            cluster="trees",
            difficulty=2,
            description="Node processing order: Root -> Left subtree -> Right subtree.",
            card=ConceptCard(
                definition="Preorder processes the current node before traversing left and right subtrees.",
                key_idea="Useful for serializing or cloning tree hierarchies.",
                worked_example="visit(node); preorder(node.left); preorder(node.right)",
                pitfall="Visiting children before recording parent value.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="preorder-processes-leaves-first",
                concept_id="binary-tree-traversal-preorder",
                description="Confuses preorder with postorder, expecting leaf nodes to be evaluated first.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="binary-tree-traversal-inorder",
            name="Binary Tree: Inorder Traversal",
            cluster="trees",
            difficulty=2,
            description="Node processing order: Left subtree -> Root -> Right subtree.",
            card=ConceptCard(
                definition="Inorder traverses the left subtree, processes the root, then traverses right.",
                key_idea="Inorder traversal of a Binary Search Tree (BST) visits nodes in sorted ascending order.",
                worked_example="inorder(node.left); visit(node); inorder(node.right)",
                pitfall="Assuming inorder gives sorted output for any arbitrary binary tree.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="inorder-always-sorted-arbitrary-tree",
                concept_id="binary-tree-traversal-inorder",
                description="Expects inorder traversal to produce sorted values on non-BST binary trees.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="binary-tree-traversal-postorder",
            name="Binary Tree: Postorder Traversal",
            cluster="trees",
            difficulty=2,
            description="Node processing order: Left subtree -> Right subtree -> Root.",
            card=ConceptCard(
                definition="Postorder processes both children before processing the parent node.",
                key_idea="Ideal for bottom-up operations like tree deletion or calculating subtree heights.",
                worked_example="postorder(node.left); postorder(node.right); visit(node)",
                pitfall="Trying to delete parent before children have been freed.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="postorder-root-first",
                concept_id="binary-tree-traversal-postorder",
                description="Assumes root is printed first in postorder traversal.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="bst-search-property",
            name="BST Search Property",
            cluster="trees",
            difficulty=2,
            description="Ordering invariant: all left subtree keys < node key < all right subtree keys.",
            card=ConceptCard(
                definition="Every node satisfies: max(left_subtree) < node.val < min(right_subtree).",
                key_idea="Enables O(h) search by eliminating half of remaining search space per step.",
                worked_example="if target < node.val: go left; elif target > node.val: go right.",
                pitfall="Only checking immediate children instead of the entire subtree invariant.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="bst-check-immediate-only",
                concept_id="bst-search-property",
                description="Only validates node.left.val < node.val without verifying full subtree bounds.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="bst-insertion",
            name="BST Insertion",
            cluster="trees",
            difficulty=3,
            description="Navigating to appropriate null leaf slot and attaching new node.",
            card=ConceptCard(
                definition="Insertion traverses search path to a leaf and attaches node preserving BST property.",
                key_idea="New values in standard BST insertion are always added as leaf nodes.",
                worked_example="if val < curr.val: if curr.left: insert(curr.left) else: curr.left = Node(val)",
                pitfall="Inserting duplicates without a defined tie-breaker convention.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="bst-insert-restructures-root",
                concept_id="bst-insertion",
                description="Believes basic BST insertion rotates or re-balances the root node.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="tree-height-depth",
            name="Tree Height vs Depth",
            cluster="trees",
            difficulty=2,
            description="Distinguishing distance from root (depth) vs distance to deepest leaf (height).",
            card=ConceptCard(
                definition="Depth is edges from root down to node; height is edges from node down to deepest leaf.",
                key_idea="Height of empty tree is -1 (or 0 depending on convention); root has depth 0.",
                worked_example="height(node) = 1 + max(height(node.left), height(node.right))",
                pitfall="Using depth when height calculation is required.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="tree-height-depth-confused",
                concept_id="tree-height-depth",
                description="Treats height and depth as synonyms that measure distance from the root.",
            ),
        ],
    ),
    # -------------------------------------------------------------------------
    # Cluster 7: graphs
    # -------------------------------------------------------------------------
    ConceptWithMisconceptions(
        concept=Concept(
            id="graph-adjacency-list",
            name="Graph Adjacency List",
            cluster="graphs",
            difficulty=2,
            description="Representing vertices and directed/undirected edges using map of neighbor lists.",
            card=ConceptCard(
                definition="Adjacency list maps each vertex to a list of adjacent neighbor vertices.",
                key_idea="Space complexity is O(V + E), optimal for sparse graphs compared to O(V^2) matrix.",
                worked_example="graph = {0: [1, 2], 1: [2], 2: []}",
                pitfall="Forgetting to add both (u, v) and (v, u) for undirected graphs.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="undirected-one-way-edge",
                concept_id="graph-adjacency-list",
                description="Adds edge in only one direction in undirected graph, breaking reachability.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="breadth-first-search-queue",
            name="Breadth-First Search (BFS)",
            cluster="graphs",
            difficulty=3,
            description="Level-order traversal using FIFO queue to find unweighted shortest paths.",
            card=ConceptCard(
                definition="BFS explores vertices in order of increasing distance from source using a FIFO queue.",
                key_idea="Guarantees finding shortest path in unweighted graphs.",
                worked_example="queue = deque([start]); visited.add(start); while queue: u = popleft()",
                pitfall="Marking vertex visited when dequeued instead of when enqueued (causing duplicate entries).",
            ),
        ),
        misconceptions=[
            Misconception(
                id="bfs-mark-visited-on-pop",
                concept_id="breadth-first-search-queue",
                description="Marks visited on dequeue instead of enqueue, exploding queue size exponentially.",
            ),
            Misconception(
                id="bfs-shortest-path-weighted",
                concept_id="breadth-first-search-queue",
                description="Believes BFS finds shortest paths on graphs with varying positive edge weights.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="depth-first-search-visited",
            name="Depth-First Search (DFS)",
            cluster="graphs",
            difficulty=3,
            description="Exploring branch depth using recursive call stack or explicit LIFO stack.",
            card=ConceptCard(
                definition="DFS explores as far along each branch as possible before backtracking.",
                key_idea="A visited set is mandatory to prevent infinite loops in cyclic graphs.",
                worked_example="visited.add(u); for v in adj[u]: if v not in visited: dfs(v)",
                pitfall="Omitting visited set on cyclic graphs causes maximum recursion depth crash.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="dfs-no-visited-set-cycles",
                concept_id="depth-first-search-visited",
                description="Omits visited set, causing infinite recursion on cyclic graphs.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="topological-sort",
            name="Topological Sorting (Kahn's Algorithm)",
            cluster="graphs",
            difficulty=4,
            description="Linear ordering of DAG vertices such that every directed edge u -> v has u before v.",
            card=ConceptCard(
                definition="Topological sort orders vertices of a Directed Acyclic Graph (DAG) by dependency.",
                key_idea="Vertices with in-degree 0 have no unmet dependencies and can be processed first.",
                worked_example="Calculate in_degrees; push 0-in-degree nodes to queue; decrement neighbors.",
                pitfall="Attempting to topologically sort a graph with directed cycles.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="topological-sort-cyclic",
                concept_id="topological-sort",
                description="Expects topological sort to succeed on graphs containing cycles.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="dijkstra-shortest-path",
            name="Dijkstra's Algorithm",
            cluster="graphs",
            difficulty=4,
            description="Single-source shortest path on graphs with non-negative edge weights using min-heap.",
            card=ConceptCard(
                definition="Dijkstra greedily extracts vertex with minimum provisional distance from a priority queue.",
                key_idea="Relaxation updates dist[v] = min(dist[v], dist[u] + weight(u, v)).",
                worked_example="heap = [(0, start)]; while heap: (d, u) = heappop(heap); if d > dist[u]: continue",
                pitfall="Dijkstra fails on graphs with negative edge weights.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="dijkstra-handles-negative-weights",
                concept_id="dijkstra-shortest-path",
                description="Assumes Dijkstra works correctly on graphs containing negative edge weights.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="cycle-detection-directed",
            name="Cycle Detection in Directed Graphs",
            cluster="graphs",
            difficulty=4,
            description="Using 3-color vertex marking (unvisited, visiting, visited) to detect back-edges.",
            card=ConceptCard(
                definition="A directed graph contains a cycle if and only if DFS encounters a back-edge.",
                key_idea="A back-edge points to an ancestor node currently in the active DFS recursion stack.",
                worked_example="if state[v] == VISITING: return True  # Cycle detected",
                pitfall="Treating cross-edges or forward-edges to finished nodes as cycle indicators.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="directed-cycle-cross-edge-confusion",
                concept_id="cycle-detection-directed",
                description="Flags already finished nodes as cycles without checking active stack state.",
            ),
        ],
    ),
    # -------------------------------------------------------------------------
    # Cluster 8: dp
    # -------------------------------------------------------------------------
    ConceptWithMisconceptions(
        concept=Concept(
            id="overlapping-subproblems",
            name="Overlapping Subproblems",
            cluster="dp",
            difficulty=3,
            description="Identifying repeated evaluations of identical subproblem instances.",
            card=ConceptCard(
                definition="A problem exhibits overlapping subproblems if a recursive solution revisits identical states.",
                key_idea="Caching answers transforms exponential O(2^N) calls into polynomial O(N) operations.",
                worked_example="In fib(5), fib(3) is computed twice independently without memoization.",
                pitfall="Using DP when subproblems do not overlap (e.g. merge sort sub-arrays are distinct).",
            ),
        ),
        misconceptions=[
            Misconception(
                id="dp-apply-to-disjoint-subproblems",
                concept_id="overlapping-subproblems",
                description="Attempts memoization on disjoint subproblems where states never repeat.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="optimal-substructure",
            name="Optimal Substructure",
            cluster="dp",
            difficulty=3,
            description="Composing globally optimal solutions from optimal solutions to subproblems.",
            card=ConceptCard(
                definition="Optimal substructure means an optimal solution contains optimal subproblem solutions.",
                key_idea="Shortest path from A to C via B requires optimal shortest path from A to B and B to C.",
                worked_example="dist(A, C) = min_B(dist(A, B) + dist(B, C)).",
                pitfall="Assuming longest simple path exhibits optimal substructure.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="all-problems-have-optimal-substructure",
                concept_id="optimal-substructure",
                description="Assumes subproblem optimality holds even when resources are constrained across paths.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="memoization-top-down",
            name="Top-Down DP (Memoization)",
            cluster="dp",
            difficulty=3,
            description="Augmenting recursive formulations with lookup table caching.",
            card=ConceptCard(
                definition="Top-down DP preserves natural recursive flow but intercepts calls to check a memo table.",
                key_idea="Check memo table before computing; store result before returning.",
                worked_example="if n in memo: return memo[n]; memo[n] = solve(n-1) + solve(n-2); return memo[n]",
                pitfall="Forgetting to store the result into the memo table before returning.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="memoization-forget-store",
                concept_id="memoization-top-down",
                description="Checks cache on entry but neglects to save computed answer into memo table on exit.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="tabulation-bottom-up",
            name="Bottom-Up DP (Tabulation)",
            cluster="dp",
            difficulty=3,
            description="Iteratively filling a table in topological dependency order without recursion.",
            card=ConceptCard(
                definition="Bottom-up DP fills a table iteratively starting from base cases up to target state.",
                key_idea="Eliminates recursion call stack overhead and allows space optimization.",
                worked_example="dp = [0] * (n + 1); dp[1] = 1; for i in range(2, n + 1): dp[i] = dp[i-1] + dp[i-2]",
                pitfall="Iterating in an order where required predecessor states are not yet computed.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="tabulation-wrong-order",
                concept_id="tabulation-bottom-up",
                description="Fills DP table in an order where dependency states have not yet been evaluated.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="dp-state-transition-1d",
            name="1D State Transitions",
            cluster="dp",
            difficulty=3,
            description="Defining mathematical recurrence relations over a single state parameter.",
            card=ConceptCard(
                definition="A recurrence defines dp[i] as a mathematical function of previous states dp[i-1], dp[i-2].",
                key_idea="Identify minimum information required to unambiguously describe subproblem state.",
                worked_example="Climbing stairs: dp[i] = dp[i-1] + dp[i-2] with base cases dp[1]=1, dp[2]=2.",
                pitfall="Missing base cases causing index out-of-bounds or zero multiplication.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="dp-transition-incomplete-branches",
                concept_id="dp-state-transition-1d",
                description="Omits valid transition choices when computing min/max over options.",
            ),
        ],
    ),
    ConceptWithMisconceptions(
        concept=Concept(
            id="dp-state-transition-2d",
            name="2D Grid & Subsequence Transitions",
            cluster="dp",
            difficulty=4,
            description="Recurrences over pairs of indices (e.g. string prefixes, grid cells, knapsack capacity).",
            card=ConceptCard(
                definition="2D DP tracks state via two parameters (e.g., dp[i][j] for string prefixes i and j).",
                key_idea="LCS: if s1[i-1] == s2[j-1]: dp[i][j] = 1 + dp[i-1][j-1] else: max(dp[i-1][j], dp[i][j-1]).",
                worked_example="dp[i][w] = max(dp[i-1][w], val[i-1] + dp[i-1][w - wt[i-1]])",
                pitfall="Confusing i and j indices or off-by-one with 1-indexed DP tables.",
            ),
        ),
        misconceptions=[
            Misconception(
                id="2d-dp-diagonal-vs-orthogonal",
                concept_id="dp-state-transition-2d",
                description="Takes diagonal step when characters mismatch instead of taking max of orthogonal cells.",
            ),
        ],
    ),
]


def get_all_concepts() -> list[Concept]:
    return [c.concept for c in DSA_CURRICULUM]


def get_concept_by_id(concept_id: str) -> Concept | None:
    for c in DSA_CURRICULUM:
        if c.concept.id == concept_id:
            return c.concept
    return None


def get_all_misconceptions() -> list[Misconception]:
    result: list[Misconception] = []
    for c in DSA_CURRICULUM:
        result.extend(c.misconceptions)
    return result


def get_misconceptions_for_concept(concept_id: str) -> list[Misconception]:
    for c in DSA_CURRICULUM:
        if c.concept.id == concept_id:
            return c.misconceptions
    return []


def get_concepts_by_cluster(cluster_name: str) -> list[Concept]:
    return [c.concept for c in DSA_CURRICULUM if c.concept.cluster == cluster_name]
