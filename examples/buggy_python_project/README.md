# Buggy Python Project (Calculator)

This is a sample project used to demonstrate and benchmark PatchPilot's self-healing repair capabilities.

## The Bug
The `add` function in `calculator.py` contains a defect where numbers are subtracted instead of added.

## Running Tests
```powershell
pytest tests/
```
`test_add` will fail, while the remaining arithmetic tests pass.
