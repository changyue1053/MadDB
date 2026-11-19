fn main() -> maddb::Result<()> {
    // Each application links MadDB independently; no MadObs daemon is needed.
    let mut db = maddb::Database::in_memory("example.app")?;
    db.put("greeting", b"hello")?;
    assert_eq!(db.get("greeting")?, Some(b"hello".to_vec()));
    Ok(())
}
