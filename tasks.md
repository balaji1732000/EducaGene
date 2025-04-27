# Video Generation Workflow Refactor Tasks

## Planning

- [x] Consolidate shared configuration into `manim_video_generator/config.py`
- [x] Define strong-typed workflow state in `manim_video_generator/state.py`
- [x] Design separate modules for each node under `manim_video_generator/nodes/`

## Implementation

- [x] Extract `setup_request_node`, `plan_video_node`, and all node functions to individual files
- [x] Update `nodes/__init__.py` to re-export all node functions
- [x] Refactor `main.py` to import node functions from `manim_video_generator.nodes`
- [x] Add graph wiring and compile `manim_graph` in `main.py`

## Testing

- [x] Write pytest unit tests for core node behaviors in `tests/nodes/test_nodes.py`
- [x] Verify all node tests pass successfully

## Next Steps

- [ ] Perform manual smoke test by running the Flask server and invoking `/generate`
- [ ] Update any additional documentation or README with usage examples 