def quick_sort(arr):
    """Sort a list in-place using quick sort algorithm."""
    def partition(low, high):
        pivot = arr[high]
        i = low - 1
        for j in range(low, high):
            if arr[j] <= pivot:
                i += 1
                arr[i], arr[j] = arr[j], arr[i]
        arr[i + 1], arr[high] = arr[high], arr[i + 1]
        return i + 1

    def sort(low, high):
        if low < high:
            pi = partition(low, high)
            sort(low, pi - 1)
            sort(pi + 1, high)

    if arr:
        sort(0, len(arr) - 1)
    return arr


if __name__ == "__main__":
    # Test examples
    print(quick_sort([3, 6, 8, 10, 1, 2, 1]))  # [1, 1, 2, 3, 6, 8, 10]
    print(quick_sort([10, 7, 8, 9, 1, 5]))      # [1, 5, 7, 8, 9, 10]
    print(quick_sort([]))                       # []
    print(quick_sort([1]))                      # [1]
