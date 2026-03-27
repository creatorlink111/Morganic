pub mod arithmetic;
pub mod errors;
pub mod parser;
pub mod splitter;
pub mod state;

pub use parser::{execute_program, try_eval_and_print_inline_expression};
pub use state::MorganicState;
