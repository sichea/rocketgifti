import { createClient } from '@supabase/supabase-js';
import { v4 as uuidv4 } from 'uuid';

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_KEY;
const supabase = createClient(supabaseUrl!, supabaseKey!);

export default async function handler(req, res) {
  if (req.method === 'POST') {
    const { goods_code, title, winner_count, admin_id } = req.body;
    const event_id = 'EV_' + uuidv4().slice(0, 8).toUpperCase();

    try {
      const { data, error } = await supabase
        .from('events')
        .insert({
          event_id,
          admin_id: admin_id || 0,
          title,
          goods_code,
          winner_count,
          status: 'OPEN'
        })
        .select();

      if (error) throw error;
      res.status(200).json(data[0]);
    } catch (error) {
      res.status(500).json({ message: error.message });
    }
  } else if (req.method === 'GET') {
    try {
      const { data, error } = await supabase
        .from('events')
        .select('*')
        .order('created_at', { ascending: false });

      if (error) throw error;
      res.status(200).json(data);
    } catch (error) {
      res.status(500).json({ message: error.message });
    }
  }
}
