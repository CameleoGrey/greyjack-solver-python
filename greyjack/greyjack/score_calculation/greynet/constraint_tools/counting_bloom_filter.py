# greynet/constraint_tools/counting_bloom_filter.py
import mmh3
from bitarray import bitarray
import math

class CountingBloomFilter:
    """
    A Counting Bloom Filter that supports adding, removing, and checking for items.
    
    This is essential for the rules engine where facts can be inserted and retracted.
    Instead of single bits, it uses a bit array to store n-bit counters.
    """
    
    def __init__(self, estimated_items: int, false_positive_rate: float, cell_bits: int = 4):
        """
        Initializes the Counting Bloom Filter.
        
        Args:
            estimated_items (int): The expected number of items to be stored.
            false_positive_rate (float): The desired false positive probability.
            cell_bits (int): The number of bits per counter cell (e.g., 4, 8).
                             This determines the max count before overflow.
        """
        if not (0 < false_positive_rate < 1):
            raise ValueError("False positive rate must be between 0 and 1.")
        if estimated_items <= 0:
            raise ValueError("Estimated items must be positive.")

        # Calculate optimal size and number of hashes
        self.size = self._get_size(estimated_items, false_positive_rate)
        self.num_hashes = self._get_hash_count(self.size, estimated_items)
        self.cell_bits = cell_bits
        self.max_count = (1 << cell_bits) - 1
        
        # The bit array size is the number of cells * bits per cell
        self.bit_array = bitarray(self.size * self.cell_bits)
        self.bit_array.setall(0)
        
        self.item_count = 0

    @staticmethod
    def _get_size(n, p):
        """Calculate bit array size (m) from items (n) and false positive rate (p)."""
        m = - (n * math.log(p)) / (math.log(2) ** 2)
        return int(math.ceil(m))

    @staticmethod
    def _get_hash_count(m, n):
        """Calculate optimal number of hash functions (k) from size (m) and items (n)."""
        k = (m / n) * math.log(2)
        return int(math.ceil(k))

    def _get_hashes(self, item_str: str) -> list[int]:
        """Generate num_hashes hash values for an item."""
        # Use two hashes to generate k hashes, a common and fast technique
        # FIX: The seed for the second hash must be an unsigned 32-bit integer.
        # By setting signed=False, we ensure h1 is always in the valid range.
        h1 = mmh3.hash(item_str, seed=0, signed=False)
        h2 = mmh3.hash(item_str, seed=h1)
        return [(h1 + i * h2) % self.size for i in range(self.num_hashes)]

    def _get_cell_value(self, index: int) -> int:
        """Reads the integer value from a counter cell."""
        start = index * self.cell_bits
        end = start + self.cell_bits
        return int.from_bytes(self.bit_array[start:end].tobytes(), 'little')

    def _set_cell_value(self, index: int, value: int):
        """Writes an integer value to a counter cell."""
        start = index * self.cell_bits
        end = start + self.cell_bits
        val_bits = bitarray()
        val_bits.frombytes(value.to_bytes(math.ceil(self.cell_bits / 8), 'little'))
        self.bit_array[start:end] = val_bits[:self.cell_bits]

    def add(self, item: any):
        """
        Adds an item to the filter by incrementing its corresponding counters.
        """
        item_str = str(item)
        hashes = self._get_hashes(item_str)
        
        # Check if all cells can be incremented before doing so
        for index in hashes:
            if self._get_cell_value(index) >= self.max_count:
                raise OverflowError(f"Counter for item '{item}' would overflow.")

        for index in hashes:
            current_value = self._get_cell_value(index)
            self._set_cell_value(index, current_value + 1)
        self.item_count += 1

    def remove(self, item: any):
        """
        Removes an item by decrementing its corresponding counters.
        Does nothing if the item was likely not present.
        """
        if item not in self:
            return

        item_str = str(item)
        hashes = self._get_hashes(item_str)
        for index in hashes:
            current_value = self._get_cell_value(index)
            if current_value > 0:
                self._set_cell_value(index, current_value - 1)
        self.item_count -= 1

    def __contains__(self, item: any) -> bool:
        """
        Checks if an item is in the filter.
        Returns False if the item is definitely not in the set.
        Returns True if the item is probably in the set (with a chance of being a false positive).
        """
        item_str = str(item)
        hashes = self._get_hashes(item_str)
        for index in hashes:
            if self._get_cell_value(index) == 0:
                return False
        return True

    def __len__(self) -> int:
        """Returns the number of items added to the filter."""
        return self.item_count
